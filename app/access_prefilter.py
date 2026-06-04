"""检索前访问控制：在向量 / BM25 打分前收窄候选 ID，避免无权 chunk 进入候选池。"""
from __future__ import annotations

import logging
from typing import Any

from llama_index.core.schema import NodeWithScore, TextNode

from app.access_control import can_access_chunk_metadata
from app.config import Settings

logger = logging.getLogger(__name__)


def resolve_allowed_node_ids(
    settings: Settings,
    *,
    roles: list[str] | None,
    tenant_id: str | None,
    security_clearance: int,
) -> frozenset[str]:
    """基于 BM25 语料元数据（与索引节点 ID 一致）计算当前用户可检索的 node_id 集合。"""
    from app.bm25_store import _get_bm25

    try:
        _, ids, meta_lookup = _get_bm25(settings)
    except FileNotFoundError:
        logger.warning("BM25 语料缺失，无法预筛候选 ID")
        return frozenset()

    allowed: set[str] = set()
    for nid in ids:
        m = meta_lookup.get(nid) or {}
        if can_access_chunk_metadata(
            m,
            roles=roles,
            tenant_id=tenant_id,
            security_clearance=security_clearance,
        ):
            allowed.add(nid)
    logger.debug("access prefilter: allowed=%s / corpus=%s", len(allowed), len(ids))
    return frozenset(allowed)


def _distance_to_similarity(distance: float | None) -> float | None:
    if distance is None:
        return None
    # Chroma 默认 cosine distance ∈ [0, 2]；转为相似度便于与历史分数尺度接近
    return max(0.0, 1.0 - float(distance))


def _vector_retrieve_qdrant_filtered(
    index: Any,
    query: str,
    top_k: int,
    settings: Settings,
    *,
    allowed_ids: frozenset[str],
) -> list[NodeWithScore]:
    from qdrant_client.models import Filter, HasIdCondition

    from app.bm25_store import _get_bm25
    from app.qdrant_index_store import get_qdrant_client

    ids_list = list(allowed_ids)
    n_results = min(top_k, len(ids_list))
    embed_model = index._embed_model
    q_emb = embed_model.get_query_embedding(query)
    client = get_qdrant_client(settings)
    coll = settings.chroma_collection_name

    response = client.query_points(
        collection_name=coll,
        query=q_emb,
        query_filter=Filter(must=[HasIdCondition(has_id=ids_list)]),
        limit=n_results,
        with_payload=True,
    )
    hits = response.points
    _, _, meta_lookup = _get_bm25(settings)
    out: list[NodeWithScore] = []
    for hit in hits:
        nid = str(hit.id)
        payload = dict(hit.payload or {})
        m = meta_lookup.get(nid) or {
            k: v for k, v in payload.items() if not str(k).startswith("_")
        }
        text = str(m.get("_bm25_text") or payload.get("text") or "")
        meta = {k: v for k, v in m.items() if k != "_bm25_text"}
        node = TextNode(text=text or "", metadata=meta, id_=nid)
        score = float(hit.score) if hit.score is not None else None
        out.append(NodeWithScore(node=node, score=score))
    return out


def vector_retrieve_access_filtered(
    index: Any,
    query: str,
    top_k: int,
    settings: Settings,
    *,
    roles: list[str] | None,
    tenant_id: str | None,
    security_clearance: int,
    allowed_ids: frozenset[str] | None = None,
) -> list[NodeWithScore]:
    """仅在 allowed_ids 子集上做向量近邻检索（Chroma ids / Qdrant HasId 预筛）。"""
    if top_k < 1:
        return []
    if allowed_ids is None:
        allowed_ids = resolve_allowed_node_ids(
            settings,
            roles=roles,
            tenant_id=tenant_id,
            security_clearance=security_clearance,
        )
    if not allowed_ids:
        return []

    if getattr(settings, "vector_backend", "chroma") == "qdrant":
        return _vector_retrieve_qdrant_filtered(
            index, query, top_k, settings, allowed_ids=allowed_ids
        )

    ids_list = list(allowed_ids)
    embed_model = index._embed_model
    q_emb = embed_model.get_query_embedding(query)

    vector_store = index.vector_store
    coll = getattr(vector_store, "_collection", None)
    if coll is None:
        n_results = min(top_k, len(ids_list))
        logger.warning("无法获取 Chroma collection，回退全库 retriever")
        retriever = index.as_retriever(similarity_top_k=n_results)
        scored = retriever.retrieve(query)
        allow = allowed_ids
        return [sn for sn in scored if sn.node.node_id in allow][:top_k]

    # BM25 语料 ID 与 Chroma 集合可能短暂不一致；仅对存在的 ID 做 query，避免 InternalError
    query_ids = ids_list
    try:
        peek = coll.get(ids=ids_list, include=[])
        present = set(peek.get("ids") or [])
        query_ids = [i for i in ids_list if i in present]
    except Exception:
        logger.exception("Chroma get(ids) 预检失败，回退全库 retriever + 内存过滤")
        retriever = index.as_retriever(similarity_top_k=min(top_k, 50))
        scored = retriever.retrieve(query)
        return [sn for sn in scored if sn.node.node_id in allowed_ids][:top_k]

    if not query_ids:
        logger.warning(
            "access prefilter: allowed=%s 但与 Chroma 无交集，返回空（请 reindex 对齐 BM25）",
            len(ids_list),
        )
        return []

    n_results = min(top_k, len(query_ids))
    results = coll.query(
        query_embeddings=[q_emb],
        n_results=n_results,
        ids=query_ids,
        include=["metadatas", "documents", "distances"],
    )
    out: list[NodeWithScore] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return out

    ids_row = results["ids"][0]
    docs_row = results.get("documents") or [[]]
    meta_row = results.get("metadatas") or [[]]
    dist_row = results.get("distances") or [[]]
    documents = docs_row[0] if docs_row else []
    metadatas = meta_row[0] if meta_row else []
    distances = dist_row[0] if dist_row else []

    for i, nid in enumerate(ids_row):
        text = documents[i] if i < len(documents) else ""
        meta = dict(metadatas[i] if i < len(metadatas) and metadatas[i] else {})
        dist = distances[i] if i < len(distances) else None
        node = TextNode(text=text or "", metadata=meta, id_=nid)
        out.append(
            NodeWithScore(node=node, score=_distance_to_similarity(dist))
        )
    return out
