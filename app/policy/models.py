"""Policy rule types and evaluation result structs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class PolicyAction(str, Enum):
    """MVP semantics (see docs/BEHAVIOR-GUARD-EVAL.md):
    — intercept: block before RAG/LLM (legacy behavior_guard).
    — warn: log + add policy_warnings; RAG proceeds.
    — allow_log: allow with audit log only.
    """

    intercept = "intercept"
    warn = "warn"
    allow_log = "allow_log"


@dataclass(frozen=True)
class PolicyRuleModel:
    id: str
    category: str
    priority: int
    risk_level: RiskLevel
    action: PolicyAction
    pattern: str | None
    template_patterns: tuple[str, ...]
    message_zh: str


@dataclass
class PolicyEvalResult:
    """Structured policy outcome for API + audit."""

    should_skip_rag: bool
    policy_action: PolicyAction | str
    policy_risk_level: str | None
    intercept_reason_code: str | None
    message_zh: str | None
    behavior: str | None  # human_review when intercept
    matched_rule_ids: list[str]
    rule_matches_detail: list[dict[str, Any]]
    winning_rule_id: str | None
    policy_warnings: list[str]
    embedding_max_sim: float | None
    embedding_hit: bool
    llm_risk_class: str | None
    llm_confidence: float | None
    llm_hit: bool
    requires_human_review: bool
    policy_hits: list[dict[str, Any]] = field(default_factory=list)
