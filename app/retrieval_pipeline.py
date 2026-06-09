"""向量 + BM25 混合召回，再 Rerank；支持中/英/德三语双知识库路由。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from llama_index.core.schema import NodeWithScore

from app.config import Settings
from app.domain_router import RouterResult, route_domains
from app.observability import log_structured_event
from app.query_rewrite import resolve_retrieval_query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredRetrieval:
    """检索+重排结果。"""

    nodes: list[NodeWithScore]
    retrieval_query: str
    router_result: RouterResult | None = None
    language: str | None = None  # "zh" | "en" | "de" | "other"
    collection_used: str | None = None


def _normalize_scores_minmax(nodes: list[NodeWithScore]) -> list[NodeWithScore]:
    """将单路召回分数线性缩放到 [0, 1]（一路内 min-max）。"""
    if not nodes:
        return []
    raw = [float(sn.score) if sn.score is not None else 0.0 for sn in nodes]
    lo, hi = min(raw), max(raw)
    if hi <= lo:
        normed = [1.0 if hi > 0.0 else 0.0 for _ in raw]
    else:
        span = hi - lo
        normed = [(x - lo) / span for x in raw]
    return [
        NodeWithScore(node=sn.node, score=float(n))
        for sn, n in zip(nodes, normed)
    ]


def _merge_hybrid_by_node_id(
    vector_scored: list[NodeWithScore],
    bm25_scored: list[NodeWithScore],
    *,
    normalize_scores: bool = True,
    fusion: str = "max",
    rrf_k: int = 60,
) -> list[NodeWithScore]:
    if fusion == "rrf":
        return _merge_hybrid_by_rrf(vector_scored, bm25_scored, k=rrf_k)

    vec = (
        _normalize_scores_minmax(vector_scored)
        if normalize_scores
        else list(vector_scored)
    )
    bm25 = (
        _normalize_scores_minmax(bm25_scored)
        if normalize_scores
        else list(bm25_scored)
    )
    by_id: dict[str, NodeWithScore] = {}
    for sn in vec:
        by_id[sn.node.node_id] = sn
    for sn in bm25:
        nid = sn.node.node_id
        prev = by_id.get(nid)
        if prev is None:
            by_id[nid] = sn
            continue
        best = max(float(prev.score or 0.0), float(sn.score or 0.0))
        by_id[nid] = NodeWithScore(node=prev.node, score=best)
    merged = list(by_id.values())
    merged.sort(key=lambda x: float(x.score or 0.0), reverse=True)
    return merged


def _merge_hybrid_by_rrf(
    vector_scored: list[NodeWithScore],
    bm25_scored: list[NodeWithScore],
    *,
    k: int = 60,
) -> list[NodeWithScore]:
    """按 RRF 融合两路召回排名，避免对齐 BM25 与向量分数尺度。"""
    k = max(1, int(k))
    by_id: dict[str, tuple[Any, float]] = {}

    def add_ranked(nodes: list[NodeWithScore]) -> None:
        seen: set[str] = set()
        for rank, sn in enumerate(nodes, start=1):
            nid = sn.node.node_id
            if nid in seen:
                continue
            seen.add(nid)
            prev = by_id.get(nid)
            score = 1.0 / (k + rank)
            if prev is None:
                by_id[nid] = (sn.node, score)
            else:
                node, total = prev
                by_id[nid] = (node, total + score)

    add_ranked(vector_scored)
    add_ranked(bm25_scored)

    merged = [
        NodeWithScore(node=node, score=score)
        for node, score in by_id.values()
    ]
    merged.sort(key=lambda x: float(x.score or 0.0), reverse=True)
    return merged



def _log_retrieve_event(
    trace_id: str | None,
    *,
    hits: int,
    retrieval_query: str,
    router_result: RouterResult | None,
) -> None:
    primary_domain = None
    if router_result is not None:
        primary_domain = router_result.primary_domain
    log_structured_event(
        trace_id,
        "retrieve",
        hits=hits,
        retrieval_query=(retrieval_query or "")[:500],
        primary_domain=primary_domain,
    )


def retrieve_scored_nodes(
    index: Any,
    user_query: str,
    top_k: int,
    settings: Settings,
    *,
    use_query_rewrite: bool | None = None,
    user_context: Any | None = None,
    skip_domain_router: bool = False,
    trace_id: str | None = None,
) -> ScoredRetrieval:
    from app.cache import (
        build_retrieval_cache_key,
        cache_get_retrieval,
        cache_put_retrieval,
    )
    from app.metrics import _RetrieveTimer, observe_retrieve
    from app.telemetry import trace_span

    cache_key = build_retrieval_cache_key(
        user_query=user_query,
        top_k=top_k,
        settings=settings,
        use_query_rewrite=use_query_rewrite,
        user_context=user_context,
        skip_domain_router=skip_domain_router,
    )
    timer = _RetrieveTimer()

    with trace_span("retrieve_scored_nodes", trace_id=trace_id, top_k=top_k):
        cached, level = cache_get_retrieval(
            cache_key, user_query=user_query, settings=settings
        )
        if cached is not None:
            observe_retrieve(timer, cache_level=level)
            return cached

        result = _retrieve_scored_nodes_impl(
            index,
            user_query,
            top_k,
            settings,
            use_query_rewrite=use_query_rewrite,
            user_context=user_context,
            skip_domain_router=skip_domain_router,
            trace_id=trace_id,
        )
        cache_put_retrieval(cache_key, user_query, result, settings)
        observe_retrieve(timer)
        return result


def _retrieve_scored_nodes_impl(
    index: Any,
    user_query: str,
    top_k: int,
    settings: Settings,
    *,
    use_query_rewrite: bool | None = None,
    user_context: Any | None = None,
    skip_domain_router: bool = False,
    trace_id: str | None = None,
) -> ScoredRetrieval:
    # ── 语言检测 + 双索引路由 ──
    from app.language_router import detect_language, get_collection_for_lang

    rq = resolve_retrieval_query(
        user_query,
        settings,
        use_rewrite=use_query_rewrite,
        trace_id=trace_id,
    )

    lang = detect_language(rq)
    lang_route = get_collection_for_lang(lang, settings)
    logger.info("语言路由: %s → collection=%s", lang, lang_route.collection_name)

    # 选择对应语言的索引
    if lang == "zh":
        from app.vector_index import get_vector_index_cn

        try:
            idx = get_vector_index_cn()
        except RuntimeError:
            logger.warning("中文索引不存在，回退到英文索引")
            idx = index
    else:
        idx = index    rr: RouterResult | None = None
    if getattr(settings, "domain_router_enabled", True) and not skip_domain_router:
        rr = route_domains(rq, settings)

    candidate_k = (
        max(top_k, settings.rerank_candidate_top_k)
        if settings.rerank_enabled
        else top_k
    )

    allowed_ids: frozenset[str] | None = None
    if user_context is not None:
        from app.access_prefilter import resolve_allowed_node_ids

        allowed_ids = resolve_allowed_node_ids(
            settings,
            roles=user_context.roles,
            tenant_id=user_context.tenant_id,
            security_clearance=user_context.security_clearance,
        )
        if not allowed_ids:
            _log_retrieve_event(trace_id, hits=0, retrieval_query=rq, router_result=rr)
            return ScoredRetrieval(
                nodes=[], retrieval_query=rq, router_result=rr,
                language=lang, collection_used=lang_route.collection_name,
            )

    if allowed_ids is not None:
        from app.access_prefilter import vector_retrieve_access_filtered

        vector_scored = vector_retrieve_access_filtered(
            idx,
            rq,
            candidate_k,
            settings,
            roles=user_context.roles,
            tenant_id=user_context.tenant_id,
            security_clearance=user_context.security_clearance,
            allowed_ids=allowed_ids,
        )
    else:
        retriever = idx.as_retriever(similarity_top_k=candidate_k)
        vector_scored = retriever.retrieve(rq)

    merged: list[NodeWithScore] = list(vector_scored)
    if settings.hybrid_bm25_enabled:
        try:
            from app.bm25_store import bm25_search, node_with_score_from_bm25, _get_bm25

            # 使用语言对应的 BM25 语料
            bm25_path = getattr(settings, "bm25_corpus_path_cn", "data/bm25_cn_corpus.jsonl") if lang == "zh" else settings.bm25_corpus_path
            bm25_hits = bm25_search(
                settings,
                rq,
                settings.bm25_candidate_top_k,
                allowed_ids=allowed_ids,
                corpus_path=bm25_path,
            )
            _, _, meta_lookup = _get_bm25(settings, corpus_path=bm25_path)
            bm25_nodes: list[NodeWithScore] = []
            for nid, bsc in bm25_hits:
                nws = node_with_score_from_bm25(nid, bsc, meta_lookup)
                if nws is not None:
                    bm25_nodes.append(nws)
            merged = _merge_hybrid_by_node_id(
                vector_scored,
                bm25_nodes,
                normalize_scores=getattr(settings, "hybrid_score_normalize", True),
                fusion=getattr(settings, "hybrid_fusion", "max"),
                rrf_k=getattr(settings, "hybrid_rrf_k", 60),
            )
            logger.debug(
                "hybrid: vec=%s bm25=%s merged=%s prefilter=%s fusion=%s lang=%s",
                len(vector_scored),
                len(bm25_nodes),
                len(merged),
                allowed_ids is not None,
                getattr(settings, "hybrid_fusion", "max"),
                lang,
            )
        except FileNotFoundError:
            logger.warning("BM25 语料未找到，仅使用向量召回（请运行 reindex.py / build_cn_index.py）")
        except Exception:
            logger.exception("BM25 分支失败，回退为纯向量候选")
            merged = list(vector_scored)

    if not merged:
        _log_retrieve_event(trace_id, hits=0, retrieval_query=rq, router_result=rr)
        return ScoredRetrieval(
            nodes=[], retrieval_query=rq, router_result=rr,
            language=lang, collection_used=lang_route.collection_name,
        )

    if (
        user_context is not None
        and getattr(settings, "access_post_filter_safety_net", False)
    ):
        from app.access_control import filter_nodes_by_access

        merged = filter_nodes_by_access(
            merged,
            roles=user_context.roles,
            tenant_id=user_context.tenant_id,
            security_clearance=user_context.security_clearance,
        )
        if not merged:
            _log_retrieve_event(trace_id, hits=0, retrieval_query=rq, router_result=rr)
            return ScoredRetrieval(
                nodes=[], retrieval_query=rq, router_result=rr,
                language=lang, collection_used=lang_route.collection_name,
            )

    from app.retrieval_intent_boost import apply_retrieval_intent_boost

    merged = apply_retrieval_intent_boost(merged, rq, settings)

    if (
        rr
        and rr.allowed_domains
        and getattr(settings, "domain_router_hard_filter", False)
    ):
        from app.access_control import filter_nodes_by_domain

        strict = getattr(settings, "domain_router_strict", False)
        before_domain = merged
        post_d = filter_nodes_by_domain(before_domain, rr.allowed_domains, strict=strict)
        if post_d:
            merged = post_d
        elif getattr(settings, "domain_router_fallback_all", True):
            logger.warning(
                "domain_router: 过滤后无候选，回退为不按 domain 过滤（primary=%s）",
                rr.primary_domain,
            )
            merged = before_domain
        else:
            merged = []

    if not merged:
        _log_retrieve_event(trace_id, hits=0, retrieval_query=rq, router_result=rr)
        return ScoredRetrieval(
            nodes=[], retrieval_query=rq, router_result=rr,
            language=lang, collection_used=lang_route.collection_name,
        )

    if settings.rerank_enabled:
        from app.rerank import rerank_nodes

        nodes = rerank_nodes(rq, merged, top_n=top_k, settings=settings)
        nodes = apply_retrieval_intent_boost(nodes, rq, settings)
        out = ScoredRetrieval(
            nodes=nodes, retrieval_query=rq, router_result=rr,
            language=lang, collection_used=lang_route.collection_name,
        )
        _log_retrieve_event(
            trace_id, hits=len(out.nodes), retrieval_query=rq, router_result=rr
        )
        return out
    out = ScoredRetrieval(
        nodes=merged[:top_k], retrieval_query=rq, router_result=rr,
        language=lang, collection_used=lang_route.collection_name,
    )
    _log_retrieve_event(
        trace_id, hits=len(out.nodes), retrieval_query=rq, router_result=rr
    )
    return out
