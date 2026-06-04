"""Demo-grade behavior guard façade (delegates to `app.policy`).

保留 `evaluate_behavior_guard` / `BehaviorGuardHit` 供旧脚本与评测导入；
生产路径请优先使用 `app.policy.evaluate_policy` 以拿到结构化护栏结果与审计字段。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.policy.engine import evaluate_policy


@dataclass(frozen=True)
class BehaviorGuardHit:
    """Structured result when a rule fires (intercept tier)."""

    reason_code: str
    behavior: str  # "human_review"
    message_zh: str


def evaluate_behavior_guard(query: str, settings: Settings) -> BehaviorGuardHit | None:
    """Return a hit if policy requests intercept; otherwise None (RAG 可继续)。"""
    res = evaluate_policy(
        query,
        settings,
        trace_id=None,
        user_context_summary=None,
        endpoint=None,
        skip_audit_log=True,
    )
    if not res.should_skip_rag:
        return None
    return BehaviorGuardHit(
        reason_code=res.intercept_reason_code or "POLICY_HIT",
        behavior="human_review",
        message_zh=(
            res.message_zh
            or "该问题涉及需人工复核的合规或安全场景，无法由自动助手直接作答。请转人工处理。"
        ),
    )
