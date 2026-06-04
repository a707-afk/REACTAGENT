"""多 Agent 骨架：supervisor 路由线性工单流或 escalation 桩节点。"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent_graph import nodes
from app.agent_graph.state import TicketAgentState
from app.config import Settings


def node_supervisor(state: TicketAgentState) -> dict[str, Any]:
    """轻量路由：显式 escalation 意图或 critical 客户 tier 走升级桩。"""
    intent = (state.get("intent") or "").strip().lower()
    tier = (state.get("customer_tier") or "").strip().lower()
    route = "escalation" if intent == "escalation" or tier == "critical" else "linear"
    return {
        "audit_trace": nodes._append_audit(
            state,
            "supervisor",
            {"route": route, "intent": intent or None, "customer_tier": tier or None},
        ),
        "_supervisor_route": route,
    }


def node_escalation(state: TicketAgentState) -> dict[str, Any]:
    """升级桩：标记人工复核并跳过 RAG。"""
    return {
        "policy_skip_rag": True,
        "human_review_required": True,
        "final_action": "escalation_stub",
        "draft_reply": "该工单已标记升级，请二线人工处理。",
        "ticket_note": "supervisor 路由至 escalation 桩节点",
        "audit_trace": nodes._append_audit(
            state,
            "escalation",
            {"human_review_required": True, "stub": True},
        ),
    }


def route_after_supervisor(state: TicketAgentState) -> str:
    if state.get("_supervisor_route") == "escalation":
        return "escalation"
    return "policy"


def build_multi_ticket_agent_graph(*, settings: Settings):
    """Supervisor → 线性 policy/retrieve/gate/draft 或 escalation 桩 → finalize。"""

    def _policy(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_policy(s, settings=settings)

    def _retrieve(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_retrieve(s, settings=settings)

    def _gate(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_evidence_gate(s, settings=settings)

    def _grader(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_grader(s, settings=settings)

    def _rewrite(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_rewrite_query(s, settings=settings)

    def _draft(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_draft(s, settings=settings)

    def _hallucination(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_hallucination(s, settings=settings)

    g: StateGraph = StateGraph(TicketAgentState)
    g.add_node("supervisor", node_supervisor)
    g.add_node("policy", _policy)
    g.add_node("retrieve", _retrieve)
    g.add_node("gate", _gate)
    g.add_node("grader", _grader)
    g.add_node("rewrite_query", _rewrite)
    g.add_node("draft", _draft)
    g.add_node("hallucination", _hallucination)
    g.add_node("escalation", node_escalation)
    g.add_node("finalize", nodes.node_finalize)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"policy": "policy", "escalation": "escalation"},
    )
    g.add_conditional_edges(
        "policy",
        nodes.route_after_policy,
        {"retrieve": "retrieve", "finalize": "finalize"},
    )
    g.add_edge("retrieve", "gate")
    g.add_conditional_edges(
        "gate",
        nodes.route_after_gate,
        {"grader": "grader", "finalize": "finalize"},
    )
    g.add_conditional_edges(
        "grader",
        nodes.route_after_grader,
        {"draft": "draft", "rewrite_query": "rewrite_query", "finalize": "finalize"},
    )
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("draft", "hallucination")
    g.add_conditional_edges(
        "hallucination",
        nodes.route_after_hallucination,
        {"finalize": "finalize"},
    )
    g.add_edge("escalation", "finalize")
    g.add_edge("finalize", END)
    return g.compile()
