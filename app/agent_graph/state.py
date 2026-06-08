"""工单 Agent 图状态（与设计文档 §状态字段 对齐）。"""
from __future__ import annotations

from typing import Any, TypedDict


class TicketAgentState(TypedDict, total=False):
    ticket_id: str
    user_query: str
    customer_id: str | None
    customer_tier: str | None
    trace_id: str | None
    top_k: int

    user_context: dict[str, Any]

    policy_skip_rag: bool
    policy_result: dict[str, Any]
    risk_level: str | None
    intent: str | None

    retrieval_query: str | None
    routed_domains: list[str]
    retrieved_chunks: list[dict[str, Any]]
    router_trace: dict[str, Any] | None

    gate_passed: bool
    gate_error_code: str | None
    ranked_quality_scores: list[float]

    # Agentic 闭环（阶段 H）
    iterations: int
    max_iterations: int
    grader_passed: bool | None
    grader_feedback: str | None
    hallucination_passed: bool | None
    hallucination_feedback: str | None
    citations: list[dict[str, Any]]
    rewrite_history: list[str]
    loop_detected: bool

    draft_reply: str | None
    required_fields: list[str]
    human_review_required: bool
    final_action: str
    ticket_note: str | None

    audit_trace: list[dict[str, Any]]

    # Agent Tools (Phase: tools integration)
    tool_calls: list[dict[str, Any]]       # LLM-decided tool invocations
    tool_results: list[dict[str, Any]]     # tool execution results
    session_id: str | None                 # multi-turn session binding
    conversation_history: str | None       # injected context for LLM prompt
