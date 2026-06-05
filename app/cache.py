"""检索结果三级缓存：L1 内存 LRU（必做）；L2 可选语义相似度缓存。

reindex 或索引变更后请调用 ``cache_clear()``（``rebuild_index`` 已自动调用）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from collections import OrderedDict
from dataclasses import asdict
from typing import Any

from llama_index.core.schema import NodeWithScore, TextNode

from app.config import Settings
from app.domain_router import RouterResult
from app.retrieval_pipeline import ScoredRetrieval

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_l1: OrderedDict[str, dict[str, Any]] = OrderedDict()
_l2_entries: list[tuple[str, list[float], dict[str, Any]]] = []


def _settings_fingerprint(settings: Settings) -> str:
    """影响检索结果的配置子集（不含密钥）。"""
    parts = {
        "hybrid_bm25": settings.hybrid_bm25_enabled,
        "hybrid_norm": settings.hybrid_score_normalize,
        "hybrid_fusion": settings.hybrid_fusion,
        "hybrid_rrf_k": settings.hybrid_rrf_k,
        "rerank": settings.rerank_enabled,
        "rerank_backend": settings.rerank_backend,
        "rerank_top": settings.rerank_candidate_top_k,
        "domain_router": settings.domain_router_enabled,
        "domain_hard": settings.domain_router_hard_filter,
        "domain_soft": settings.domain_router_soft_boost_enabled,
        "intent_boost": settings.retrieval_intent_boost_enabled,
        "access_safety": settings.access_post_filter_safety_net,
        "rewrite_mode": settings.query_rewrite_mode,
        "vector_backend": settings.vector_backend,
    }
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _user_context_fingerprint(user_context: Any | None) -> str:
    if user_context is None:
        return "none"
    roles = tuple(sorted(str(r) for r in (getattr(user_context, "roles", None) or ())))
    return "|".join(
        [
            str(getattr(user_context, "tenant_id", "") or ""),
            str(getattr(user_context, "security_clearance", "") or ""),
            ",".join(roles),
        ]
    )


def build_retrieval_cache_key(
    *,
    user_query: str,
    top_k: int,
    settings: Settings,
    use_query_rewrite: bool | None = None,
    user_context: Any | None = None,
    skip_domain_router: bool = False,
) -> str:
    """L1 键：原始 query + 检索相关 settings + 访问上下文。"""
    payload = {
        "q": (user_query or "").strip(),
        "top_k": top_k,
        "rewrite": use_query_rewrite,
        "skip_router": skip_domain_router,
        "uc": _user_context_fingerprint(user_context),
        "cfg": _settings_fingerprint(settings),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _serialize_router(rr: RouterResult | None) -> dict[str, Any] | None:
    if rr is None:
        return None
    return {
        "allowed_domains": list(rr.allowed_domains),
        "primary_domain": rr.primary_domain,
        "confidence": rr.confidence,
        "method": rr.method,
        "raw_confidence": rr.raw_confidence,
        "domain_weights": [list(p) for p in rr.domain_weights],
        "routing_trace": rr.routing_trace,
    }


def _deserialize_router(data: dict[str, Any] | None) -> RouterResult | None:
    if not data:
        return None
    dw = data.get("domain_weights") or []
    weights = tuple((str(a), float(b)) for a, b in dw)
    return RouterResult(
        allowed_domains=tuple(str(d) for d in (data.get("allowed_domains") or ())),
        primary_domain=data.get("primary_domain"),
        confidence=float(data.get("confidence") or 0.0),
        method=str(data.get("method") or ""),
        raw_confidence=data.get("raw_confidence"),
        domain_weights=weights,
        routing_trace=data.get("routing_trace"),
    )


def _serialize_sr(sr: ScoredRetrieval) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for sn in sr.nodes:
        node = sn.node
        nodes.append(
            {
                "text": node.get_content(),
                "node_id": node.node_id,
                "metadata": dict(node.metadata or {}),
                "score": float(sn.score) if sn.score is not None else None,
            }
        )
    return {
        "nodes": nodes,
        "retrieval_query": sr.retrieval_query,
        "router": _serialize_router(sr.router_result),
    }


def _deserialize_sr(data: dict[str, Any]) -> ScoredRetrieval:
    scored: list[NodeWithScore] = []
    for row in data.get("nodes") or []:
        node = TextNode(
            text=str(row.get("text") or ""),
            metadata=dict(row.get("metadata") or {}),
            id_=str(row.get("node_id") or ""),
        )
        sc = row.get("score")
        scored.append(
            NodeWithScore(node=node, score=float(sc) if sc is not None else None)
        )
    return ScoredRetrieval(
        nodes=scored,
        retrieval_query=str(data.get("retrieval_query") or ""),
        router_result=_deserialize_router(data.get("router")),
    )


def _l1_get(key: str, *, max_entries: int) -> ScoredRetrieval | None:
    with _lock:
        if key not in _l1:
            return None
        _l1.move_to_end(key)
        return _deserialize_sr(_l1[key])


def _l1_put(key: str, sr: ScoredRetrieval, *, max_entries: int) -> None:
    with _lock:
        if key in _l1:
            _l1.move_to_end(key)
        _l1[key] = _serialize_sr(sr)
        while len(_l1) > max(1, max_entries):
            _l1.popitem(last=False)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (na * nb)


def _l2_get(
    query: str,
    settings: Settings,
) -> tuple[ScoredRetrieval | None, str | None]:
    if not settings.cache_semantic_enabled:
        return None, None
    threshold = float(settings.cache_semantic_threshold)
    max_entries = settings.cache_semantic_max_entries
    try:
        from app.embeddings import get_embedding_model

        emb = get_embedding_model().get_query_embedding(query)
    except Exception as exc:
        logger.debug("semantic cache embed skip: %s", exc)
        return None, None

    with _lock:
        best_idx = -1
        best_sim = 0.0
        for i, (_k, vec, _payload) in enumerate(_l2_entries):
            sim = _cosine(emb, vec)
            if sim > best_sim:
                best_sim = sim
                best_idx = i
        if best_idx < 0 or best_sim < threshold:
            return None, None
        _k, _vec, payload = _l2_entries[best_idx]
        _l2_entries.pop(best_idx)
        _l2_entries.append((_k, _vec, payload))
        return _deserialize_sr(payload), "l2"


def _l2_put(key: str, query: str, sr: ScoredRetrieval, settings: Settings) -> None:
    if not settings.cache_semantic_enabled:
        return
    max_entries = settings.cache_semantic_max_entries
    try:
        from app.embeddings import get_embedding_model

        emb = get_embedding_model().get_query_embedding(query)
    except Exception as exc:
        logger.debug("semantic cache embed put skip: %s", exc)
        return

    payload = _serialize_sr(sr)
    with _lock:
        _l2_entries.append((key, list(emb), payload))
        while len(_l2_entries) > max(1, max_entries):
            _l2_entries.pop(0)


def cache_get_retrieval(
    key: str,
    *,
    user_query: str,
    settings: Settings,
) -> tuple[ScoredRetrieval | None, str | None]:
    """返回 (结果, 命中层级 l1|l2)。"""
    if not settings.cache_enabled:
        return None, None
    hit = _l1_get(key, max_entries=settings.cache_max_entries)
    if hit is not None:
        return hit, "l1"
    return _l2_get(user_query, settings)


def cache_put_retrieval(
    key: str,
    user_query: str,
    sr: ScoredRetrieval,
    settings: Settings,
) -> None:
    if not settings.cache_enabled:
        return
    _l1_put(key, sr, max_entries=settings.cache_max_entries)
    _l2_put(key, user_query, sr, settings)


def cache_clear() -> None:
    """索引重建或语料变更后调用，清空 L1/L2。"""
    with _lock:
        _l1.clear()
        _l2_entries.clear()
    logger.info("retrieval cache cleared (L1 + L2)")


def cache_stats() -> dict[str, int]:
    with _lock:
        return {"l1_entries": len(_l1), "l2_entries": len(_l2_entries)}
