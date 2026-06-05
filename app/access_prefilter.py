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
    return _vector_retrieve_qdrant_filtered(
        index, query, top_k, settings, allowed_ids=allowed_ids
    )
    if not allowed_ids:
        return []
    return _vector_retrieve_qdrant_filtered(
        index, query, top_k, settings, allowed_ids=allowed_ids
    )
