"""多领域路由：关键词多域打分 + 可选 Embedding 相似度融合 + LLM fallback + 置信校准."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.embedding_router import score_domains_via_embedding
from app.router_calibration import calibrate_probability
from app.router_profiles import load_domain_router_profiles

logger = logging.getLogger(__name__)

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "customer_service": ("客服", "客户", "登录", "密码", "验证码", "账号", "账单", "发票", "退款"),
    "ticket_workflow": ("工单", "P0", "P1", "SLA", "升级", "事故", "故障", "incident"),
    "internal_policy": ("制度", "数据分级", "权限", "知识库", "metadata", "治理"),
    "security": ("审计", "脱敏", "注入", "prompt", "安全", "泄露"),
    "ai_governance": ("上线", "评审", "RAG 评估", "Agent", "人工审核"),
    "product": ("API", "幂等", "套餐", "基础版", "私有化"),
    "operations": ("导入", "索引", "向量", "重建", "成本", "限流", "路由"),
    "agent_design": ("LangGraph", "节点", "工作流"),
    "case": ("案例", "复盘", "bad case"),
}

_KNOWN_DOMAINS = tuple(sorted(_DOMAIN_KEYWORDS.keys()))


@dataclass(frozen=True)
class RouterResult:
    """routing_trace 内含多阶段分数，便于离线分析与校准集构建。"""

    allowed_domains: tuple[str, ...]
    primary_domain: str | None
    confidence: float
    method: str
    raw_confidence: float | None = None
    domain_weights: tuple[tuple[str, float], ...] = ()
    routing_trace: dict[str, Any] | None = None


def _rule_scores(query: str) -> dict[str, float]:
    q = query.lower()
    scores: dict[str, float] = {d: 0.0 for d in _KNOWN_DOMAINS}
    for dom, kws in _DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in q:
                scores[dom] += 1.0
            elif kw in query:
                scores[dom] += 1.0
    return scores


def _legacy_route(text: str, settings: Settings) -> RouterResult:
    scores = _rule_scores(text)
    best_dom = max(scores, key=lambda k: scores[k])
    best_score = scores[best_dom]
    total = sum(scores.values()) or 1.0
    raw_rule = float(min(1.0, max(0.0, best_score / max(total, 1e-9))))
    trace: dict[str, Any] = {
        "path": "legacy",
        "rule_scores": dict(scores),
    }

    if best_score >= 2.0 or (
        best_score >= 1.0 and sum(1 for v in scores.values() if v > 0) == 1
    ):
        cal, raw = calibrate_probability(raw_rule, branch="rules")
        trace["confidence_branch"] = "rules"
        return RouterResult(
            allowed_domains=(best_dom,),
            primary_domain=best_dom,
            confidence=cal,
            raw_confidence=raw,
            method="legacy_rules",
            domain_weights=((best_dom, best_score / max(total, 1e-9)),),
            routing_trace=trace,
        )

    if settings.zhipuai_api_key:
        picked = _llm_pick_domain(text, settings)
        if picked:
            cal, raw = calibrate_probability(0.75, branch="llm")
            trace["confidence_branch"] = "llm"
            trace["llm_domain"] = picked
            return RouterResult(
                allowed_domains=(picked,),
                primary_domain=picked,
                confidence=cal,
                raw_confidence=raw,
                method="legacy_llm",
                domain_weights=((picked, raw),),
                routing_trace=trace,
            )

    trace["confidence_branch"] = "none"
    return RouterResult((), None, 0.0, "legacy_none", raw_confidence=None, routing_trace=trace)


def _llm_pick_domain(query: str, settings: Settings) -> str | None:
    picked = _llm_pick_domains_struct(query, settings, multi=False)
    return picked[0] if picked else None


def _llm_pick_domains_struct(
    query: str,
    settings: Settings,
    *,
    multi: bool,
    max_domains: int = 3,
) -> tuple[str, ...]:
    if not settings.zhipuai_api_key:
        return ()
    from app.llm_zhipu import chat_completion

    dom_list = list(_KNOWN_DOMAINS)
    if multi:
        sys_p = (
            "你是企业知识库领域分类器。仅从给定 domain 列表中选择最相关的若干个（1~"
            + str(max_domains)
            + "），输出严格 JSON："
            '{"primary":"...", "domains":["..."]}'
            "，domains 按相关度排序，勿输出其它文字。"
        )
    else:
        sys_p = (
            "你是企业知识库领域分类器。只从给定 domain 列表中选一个最相关的，"
            '输出严格 JSON：{"domain":"..."}，不要其它文字。'
        )
    user_p = f"domain 列表：{dom_list}\n用户问题：{query.strip()}"
    try:
        raw = chat_completion(sys_p, user_p)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return ()
        obj = json.loads(m.group())
        if multi:
            primary = obj.get("primary")
            domains = obj.get("domains") or []
            ordered: list[str] = []
            if isinstance(primary, str) and primary in _DOMAIN_KEYWORDS:
                ordered.append(primary)
            if isinstance(domains, list):
                for d in domains:
                    if isinstance(d, str) and d in _DOMAIN_KEYWORDS and d not in ordered:
                        ordered.append(d)
            return tuple(ordered[:max_domains])
        d = obj.get("domain")
        if isinstance(d, str) and d in dom_list:
            return (d,)
    except Exception:  # noqa: BLE001
        logger.exception("domain router LLM 失败")
    return ()


def _normalize_scores(d: dict[str, float]) -> dict[str, float]:
    mx = max(d.values()) if d else 0.0
    if mx <= 1e-12:
        return {k: 0.0 for k in d}
    return {k: float(v / mx) for k, v in d.items()}


def _weighted_fuse(
    rules_n: dict[str, float],
    emb_n: dict[str, float],
    *,
    wr: float,
    we: float,
    multipliers: dict[str, float],
    domains: tuple[str, ...],
) -> dict[str, float]:
    out: dict[str, float] = {}
    wr = float(wr)
    we = float(we)
    s_wr = wr + we
    wr, we = wr / max(s_wr, 1e-9), we / max(s_wr, 1e-9)
    for dom in domains:
        r = rules_n.get(dom, 0.0)
        e = emb_n.get(dom, 0.0)
        m = float(multipliers.get(dom, 1.0))
        fused = wr * r + we * e * m
        out[dom] = fused
    return out


def _pick_multidomain_allowed(
    fused: dict[str, float],
    *,
    primary_domain: str,
    ratio: float,
    top_k: int,
    min_floor: float = 1e-6,
) -> tuple[str, ...]:
    pv = fused.get(primary_domain, 0.0)
    if pv <= min_floor:
        return ()
    thr = max(pv * float(ratio), min_floor)
    ranked = sorted(((d, fused[d]) for d in fused if fused[d] >= thr), key=lambda x: x[1], reverse=True)
    ordered = tuple(d for d, _ in ranked[: max(1, int(top_k))])
    return ordered if ordered else (primary_domain,)


def route_domains(query: str, settings: Settings) -> RouterResult:
    text = (query or "").strip()
    if not text:
        return RouterResult(
            (),
            None,
            0.0,
            "none",
            raw_confidence=None,
            routing_trace={"path": "empty"},
        )

    enhanced = getattr(settings, "domain_router_enhanced", True)
    if not enhanced:
        return _legacy_route(text, settings)

    profiles = load_domain_router_profiles()
    trace: dict[str, Any] = {"path": "enhanced"}

    domains: tuple[str, ...] = profiles.domains if profiles else _KNOWN_DOMAINS
    mult_map = profiles.weight_multipliers if profiles else {d: 1.0 for d in domains}
    protos = profiles.prototypes if profiles else {}

    raw_scores = _rule_scores(text)
    total_kw = sum(raw_scores.values()) or 1.0
    best_dom_kw = max(raw_scores, key=lambda k: raw_scores[k])
    rule_raw_primary = float(
        max(0.0, min(1.0, raw_scores[best_dom_kw] / max(total_kw, 1e-9)))
    )
    rule_norm = _normalize_scores({d: raw_scores[d] for d in domains})

    emb_scores: dict[str, float] = {}
    emb_diag: dict[str, Any] = {}
    embedding_on = getattr(settings, "domain_router_embedding_enabled", True)
    if embedding_on:
        protos_use = protos or {}
        emb_scores, emb_diag = score_domains_via_embedding(
            text, settings=settings, domains=domains, prototypes=protos_use
        )
    trace["embedding_diag"] = emb_diag
    emb_norm = _normalize_scores({d: emb_scores.get(d, 0.0) for d in domains})

    wr = getattr(settings, "domain_router_fusion_rule_weight", 0.55)
    we = getattr(settings, "domain_router_fusion_embedding_weight", 0.45)

    fused_raw = _weighted_fuse(rule_norm, emb_norm, wr=wr, we=we, multipliers=mult_map, domains=domains)
    trace["rule_norm"] = rule_norm
    trace["embedding_norm"] = emb_norm
    trace["fusion_weights"] = {"rule": wr, "embedding": we}
    trace["domain_weight_multipliers"] = {d: float(mult_map.get(d, 1.0)) for d in domains}
    trace["fused_before_cal"] = dict(fused_raw)

    primary = max(fused_raw, key=lambda k: fused_raw[k])
    fused_max_raw = fused_raw[primary]

    llm_fallback = getattr(settings, "domain_router_llm_fallback_enabled", True)
    fused_thr = getattr(settings, "domain_router_fused_fallback_llm_threshold", 0.22)
    emb_max = max(emb_scores.values()) if emb_scores else 0.0
    emb_thr = getattr(settings, "domain_router_embedding_fallback_llm_max_sim", 0.38)

    strong_kw = raw_scores[best_dom_kw] >= 2.0 or (
        raw_scores[best_dom_kw] >= 1.0
        and sum(1 for v in raw_scores.values() if v > 0) == 1
    )

    embedding_diag_ok = bool(embedding_on and not emb_diag.get("skipped") and emb_scores)
    embedding_weak = bool(embedding_diag_ok and emb_max < emb_thr)

    should_llm = (
        llm_fallback
        and settings.zhipuai_api_key
        and fused_max_raw < 0.88
        and not strong_kw
        and (
            fused_max_raw < fused_thr or (embedding_weak and fused_max_raw < 0.52)
        )
    )

    if should_llm:
        picked_tuple = _llm_pick_domains_struct(
            text, settings, multi=True, max_domains=int(settings.domain_router_top_domains_k or 3)
        )
        if picked_tuple:
            cal, raw = calibrate_probability(0.75, branch="llm")
            merged_weights = tuple((d, raw) for d in picked_tuple)
            trace["fallback"] = "llm_structure"
            trace["llm_domains"] = list(picked_tuple)
            trace["confidence_branch"] = "llm"
            return RouterResult(
                allowed_domains=picked_tuple,
                primary_domain=picked_tuple[0],
                confidence=cal,
                raw_confidence=raw,
                method="llm_multi",
                domain_weights=merged_weights,
                routing_trace=trace,
            )

    cal_prob, _ = calibrate_probability(float(fused_max_raw), branch="merged")
    trace["confidence_branch"] = "merged"
    secondary_ratio = getattr(settings, "domain_router_multidomain_secondary_ratio", 0.45)
    tk = int(settings.domain_router_top_domains_k or 3)
    allowed_tuple = _pick_multidomain_allowed(
        fused_raw,
        primary_domain=primary,
        ratio=float(secondary_ratio),
        top_k=tk,
    )

    merged_weights_sorted = tuple(
        sorted(((d, fused_raw[d]) for d in allowed_tuple), key=lambda x: x[1], reverse=True)
    )

    trace["rule_raw_primary"] = rule_raw_primary
    trace["raw_fused_peak"] = float(fused_max_raw)
    return RouterResult(
        allowed_domains=allowed_tuple if allowed_tuple else (),
        primary_domain=primary if allowed_tuple else None,
        confidence=cal_prob,
        raw_confidence=float(fused_max_raw),
        method="fused",
        domain_weights=merged_weights_sorted,
        routing_trace=trace,
    )
