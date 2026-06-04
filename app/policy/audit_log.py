"""Structured audit logging for policy evaluation."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.policy.models import PolicyEvalResult

_audit_logger = logging.getLogger("app.policy.audit")


def log_policy_event(
    settings: Settings,
    *,
    trace_id: str | None,
    user_context_summary: dict[str, Any] | None,
    result: PolicyEvalResult,
    endpoint: str | None = None,
) -> None:
    """Emit one JSON line: event=policy_eval with sanitized context."""
    row: dict[str, Any] = {
        "event": "policy_eval",
        "trace_id": trace_id,
        "endpoint": endpoint,
        "final_action": str(result.policy_action),
        "should_skip_rag": result.should_skip_rag,
        "policy_risk_level": result.policy_risk_level,
        "requires_human_review": result.requires_human_review,
        "matched_rules": list(result.matched_rule_ids),
        "winning_rule_id": result.winning_rule_id,
        "embedding_max_sim": result.embedding_max_sim,
        "embedding_hit": result.embedding_hit,
        "llm_class": result.llm_risk_class,
        "llm_confidence": result.llm_confidence,
        "llm_hit": result.llm_hit,
        "policy_warnings": list(result.policy_warnings),
        "user_context": _sanitize_context(user_context_summary),
    }
    _audit_logger.info("%s", json.dumps(row, ensure_ascii=False))


def _sanitize_context(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ctx:
        return None
    safe: dict[str, Any] = {}
    if tid := ctx.get("tenant_id"):
        safe["tenant_id"] = tid
    if roles := ctx.get("roles"):
        safe["roles"] = roles
    if dept := ctx.get("department"):
        safe["department"] = dept
    if "security_clearance" in ctx:
        safe["security_clearance"] = ctx.get("security_clearance")
    # Deliberately omit user_id / PII-like fields unless needed later.
    return safe or None
