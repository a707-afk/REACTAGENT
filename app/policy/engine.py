"""Multi-stage enterprise policy evaluation: rules → embedding → LLM."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.policy.audit_log import log_policy_event
from app.policy.loader import RulesBundle, compile_rule_patterns, load_rules_bundle
from app.policy.llm_classify import classify_policy_risk_llm
from app.policy.models import PolicyAction, PolicyEvalResult, PolicyRuleModel, RiskLevel

_WARN_MSG_ZH_DEFAULT = (
    "该表述可能触发合规或流程边界场景，系统将尝试检索知识库作答；请以正式流程与对内制度为准。"
)
_EMBEDDING_INTERCEPT_MSG = (
    "该问题与高风险策略话术高度相近，暂不执行自动检索。请转人工或按内部流程处理。"
)
_LLM_INTERCEPT_MSG = (
    "语义策略判定为高/中风险，暂不执行自动检索。请转人工复核。"
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


PhraseEmbCacheKey = tuple[str, str]
_phrase_embedding_cache: dict[PhraseEmbCacheKey, tuple[float, ...]] = {}


@dataclass
class MatchedRule:
    rule: PolicyRuleModel


def _category_rank(bundle: RulesBundle, category: str) -> int:
    try:
        return bundle.category_order.index(category)
    except ValueError:
        return 9999


def _collect_rule_matches(bundle: RulesBundle, text: str) -> list[MatchedRule]:
    hits: list[MatchedRule] = []
    seen: set[str] = set()
    for rule in bundle.rules:
        compiled = compile_rule_patterns(rule)
        if not compiled:
            continue
        matched = False
        for cx in compiled:
            try:
                if cx.search(text):
                    matched = True
                    break
            except re.error:
                continue
        if matched and rule.id not in seen:
            seen.add(rule.id)
            hits.append(MatchedRule(rule=rule))
    return hits


def _pick_winning_rule(bundle: RulesBundle, matches: list[MatchedRule]) -> MatchedRule | None:
    if not matches:
        return None

    def sort_key(m: MatchedRule):
        return (
            -m.rule.priority,
            _category_rank(bundle, m.rule.category),
            m.rule.id,
        )

    return sorted(matches, key=sort_key)[0]


def _risk_to_bucket(rlv: RiskLevel | str | None) -> str | None:
    if rlv is None:
        return None
    if isinstance(rlv, RiskLevel):
        return rlv.value
    return str(rlv).strip().lower()


def _flat_canonical(bundle: RulesBundle) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for cat, phrases in bundle.canonical_phrases.items():
        for p in phrases:
            out.append((cat, p))
    return out


def _embedding_guard(
    query: str,
    settings: Settings,
    bundle: RulesBundle,
) -> tuple[float | None, str | None, str | None]:
    """Returns (max_sim, best_category, best_phrase)."""
    if not settings.policy_embedding_guard_enabled:
        return None, None, None
    flat = _flat_canonical(bundle)
    if not flat:
        return None, None, None
    try:
        from app.embeddings import get_embedding_model
    except Exception:
        return None, None, None

    try:
        model = get_embedding_model()
        model_path = settings.qwen_embedding_model_path
        q_vec = list(model.get_query_embedding(query.strip()))
        best_sim = -1.0
        best_cat: str | None = None
        best_phr: str | None = None

        def phrase_vec(ph: str) -> list[float]:
            key: PhraseEmbCacheKey = (model_path, ph)
            tup = _phrase_embedding_cache.get(key)
            if tup is None:
                v = list(model.get_query_embedding(ph))
                tup = tuple(v)
                _phrase_embedding_cache[key] = tup
            return list(tup)

        for cat, phrase in flat:
            pv = phrase_vec(phrase)
            sim = cosine_similarity(q_vec, pv)
            if sim > best_sim:
                best_sim = sim
                best_cat = cat
                best_phr = phrase
        if best_sim >= settings.policy_embedding_threshold:
            return best_sim, best_cat, best_phr
        return best_sim if best_sim >= 0 else None, None, None
    except Exception:
        return None, None, None


def _embedding_intercepts(settings: Settings) -> bool:
    return bool(settings.policy_embedding_guard_enabled)


def _should_llm_intercept(cls: str | None, conf: float | None, settings: Settings) -> bool:
    if cls is None or conf is None:
        return False
    if conf < settings.policy_llm_confidence_threshold:
        return False
    return cls in ("medium", "high")


def evaluate_policy(
    query: str,
    settings: Settings,
    *,
    trace_id: str | None = None,
    user_context_summary: dict[str, Any] | None = None,
    endpoint: str | None = None,
    skip_audit_log: bool = False,
) -> PolicyEvalResult:
    """Evaluate policy pipeline. MVP: intercept skips RAG; warn logs + proceeds with retrieval."""
    from app.telemetry import trace_span

    with trace_span(
        "evaluate_policy",
        trace_id=trace_id,
        endpoint=endpoint or "",
    ):
        return _evaluate_policy_impl(
            query,
            settings,
            trace_id=trace_id,
            user_context_summary=user_context_summary,
            endpoint=endpoint,
            skip_audit_log=skip_audit_log,
        )


def _evaluate_policy_impl(
    query: str,
    settings: Settings,
    *,
    trace_id: str | None = None,
    user_context_summary: dict[str, Any] | None = None,
    endpoint: str | None = None,
    skip_audit_log: bool = False,
) -> PolicyEvalResult:
    if not getattr(settings, "behavior_guard_enabled", True):
        return _allow_empty()

    text = (query or "").strip()
    if not text:
        return _allow_empty()

    bundle = load_rules_bundle(settings)
    matches = _collect_rule_matches(bundle, text)
    winner_m = _pick_winning_rule(bundle, matches)

    matched_ids = [m.rule.id for m in matches]
    rule_detail = [
        {
            "source": "rule",
            "rule_id": m.rule.id,
            "category": m.rule.category,
            "priority": m.rule.priority,
            "risk_level": _risk_to_bucket(m.rule.risk_level),
            "action": str(m.rule.action.value),
            "is_winner": bool(winner_m and m.rule.id == winner_m.rule.id),
        }
        for m in sorted(
            matches,
            key=lambda x: (-x.rule.priority, _category_rank(bundle, x.rule.category), x.rule.id),
        )
    ]

    embedding_max_sim: float | None = None
    embedding_cat: str | None = None
    embedding_hit = False

    llm_class: str | None = None
    llm_confidence: float | None = None
    llm_hit = False

    policy_hits: list[dict[str, Any]] = list(rule_detail)
    policy_warnings: list[str] = []

    ruling_action = PolicyAction.allow_log
    ruling_risk: str | None = None
    winning_rule_id: str | None = None
    message_zh: str | None = None

    intercept = False

    # --- Rule tier (winner by max priority) ---
    if winner_m:
        ruling_action = winner_m.rule.action
        winning_rule_id = winner_m.rule.id
        ruling_risk = _risk_to_bucket(winner_m.rule.risk_level)
        message_zh = winner_m.rule.message_zh
        if winner_m.rule.action == PolicyAction.intercept:
            intercept = True
        elif winner_m.rule.action == PolicyAction.warn:
            policy_warnings.append(_WARN_MSG_ZH_DEFAULT)

    rule_intercept = intercept

    # --- OPA tier（规则层之后；默认 fail-open）---
    if getattr(settings, "opa_enabled", False) and not rule_intercept:
        from app.opa.client import query_opa_allow

        opa_input: dict[str, Any] = {
            "query": text,
            "user_context": user_context_summary or {},
            "matched_rule_ids": matched_ids,
            "winning_rule_id": winning_rule_id,
        }
        allow, opa_result, opa_err = query_opa_allow(settings, input_payload=opa_input)
        if allow is False:
            intercept = True
            ruling_action = PolicyAction.intercept
            ruling_risk = ruling_risk or "high"
            message_zh = message_zh or "外部策略（OPA）拒绝该请求。"
            winning_rule_id = winning_rule_id or "OPA_DENY"
            policy_hits.append(
                {
                    "source": "opa",
                    "allow": False,
                    "result": opa_result,
                }
            )
        elif allow is None and opa_err and not getattr(settings, "opa_fail_open", True):
            intercept = True
            ruling_action = PolicyAction.intercept
            ruling_risk = ruling_risk or "high"
            message_zh = message_zh or "外部策略（OPA）不可用，已按 fail-closed 拦截。"
            winning_rule_id = winning_rule_id or "OPA_UNAVAILABLE"
            policy_hits.append(
                {
                    "source": "opa",
                    "allow": None,
                    "error": opa_err,
                }
            )
        elif allow is True:
            policy_hits.append({"source": "opa", "allow": True})

    # --- Embedding tier (after rules/OPA — only when not already intercept) ---
    if not intercept:
        emb_sim, emb_cat, emb_phr = _embedding_guard(query, settings, bundle)
        embedding_max_sim = emb_sim
        embedding_cat = emb_cat
        if (
            embedding_max_sim is not None
            and embedding_max_sim >= settings.policy_embedding_threshold
            and emb_cat is not None
        ):
            embedding_hit = True
            intercept = True
            policy_hits.append(
                {
                    "source": "embedding",
                    "max_cosine_similarity": round(embedding_max_sim, 4),
                    "category": emb_cat,
                    "matched_canonical_hint": emb_phr,
                    "threshold": settings.policy_embedding_threshold,
                }
            )
            ruling_action = PolicyAction.intercept
            ruling_risk = ruling_risk or "high"
            message_zh = _EMBEDDING_INTERCEPT_MSG
            winning_rule_id = winning_rule_id or "POLICY_EMBEDDING_SIMILARITY"

    # --- LLM tier ---
    if not intercept and getattr(settings, "policy_llm_guard_enabled", False):
        llm_class, llm_confidence = classify_policy_risk_llm(query)
        if _should_llm_intercept(llm_class, llm_confidence, settings):
            llm_hit = True
            intercept = True
            ruling_action = PolicyAction.intercept
            ruling_risk = llm_class or "high"
            message_zh = _LLM_INTERCEPT_MSG
            winning_rule_id = winning_rule_id or "POLICY_LLM_CLASSIFIER"
            policy_hits.append(
                {
                    "source": "llm_classifier",
                    "risk_class": llm_class,
                    "confidence": llm_confidence,
                    "threshold": settings.policy_llm_confidence_threshold,
                }
            )

    requires_human_review = (
        intercept
        or embedding_hit
        or llm_hit
        or ruling_action == PolicyAction.warn
    )

    if intercept:
        prisk = ruling_risk or "high"
    elif policy_warnings:
        prisk = ruling_risk or "medium"
    else:
        prisk = ruling_risk or "low"

    result = PolicyEvalResult(
        should_skip_rag=intercept,
        policy_action=ruling_action,
        policy_risk_level=prisk,
        intercept_reason_code=winning_rule_id if intercept else None,
        message_zh=message_zh if intercept else None,
        behavior="human_review" if intercept else None,
        matched_rule_ids=matched_ids,
        rule_matches_detail=rule_detail,
        winning_rule_id=winning_rule_id,
        policy_warnings=policy_warnings,
        embedding_max_sim=embedding_max_sim,
        embedding_hit=embedding_hit,
        llm_risk_class=llm_class,
        llm_confidence=llm_confidence,
        llm_hit=llm_hit,
        requires_human_review=requires_human_review,
        policy_hits=policy_hits,
    )

    if not skip_audit_log:
        log_policy_event(
            settings,
            trace_id=trace_id,
            user_context_summary=user_context_summary,
            result=result,
            endpoint=endpoint,
        )

    return result


def _allow_empty() -> PolicyEvalResult:
    return PolicyEvalResult(
        should_skip_rag=False,
        policy_action=PolicyAction.allow_log,
        policy_risk_level=None,
        intercept_reason_code=None,
        message_zh=None,
        behavior=None,
        matched_rule_ids=[],
        rule_matches_detail=[],
        winning_rule_id=None,
        policy_warnings=[],
        embedding_max_sim=None,
        embedding_hit=False,
        llm_risk_class=None,
        llm_confidence=None,
        llm_hit=False,
        requires_human_review=False,
        policy_hits=[],
    )
