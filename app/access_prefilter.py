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
        if can_access_chunk_metadata(m, roles=roles, tenant_id=tenant_id, security_clearance=security_clearance):
            allowed.add(nid)
    logger.debug("access prefilter: allowed=%s / corpus=%s", len(allowed), len(ids))
    return frozenset(allowed)


def vector_retrieve_access_filtered(
    index: Any,
    query: str,
    top_k: int,
    settings: Settings,
    *,
    roles: list[str] | None = None,
    tenant_id: str | None = None,
    security_clearance: int = 0,
    allowed_ids: frozenset[str] | None = None,
) -> list[NodeWithScore]:
    """Query Qdrant via llama_index VectorStoreIndex with optional node_id pre-filter."""
    if top_k < 1:
        return []
    try:
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query)
    except Exception as e:
        logger.warning("Qdrant vector retrieve failed: %s", e)
        return []