"""编译 LangGraph 工单工作流。"""
from __future__ import annotations

import logging

from typing import Any, AsyncIterator

from langgraph.graph import END, START, StateGraph

from app.agent_graph import nodes
from app.agent_graph.state import TicketAgentState
from app.config import Settings, get_settings


def build_ticket_agent_graph(*, settings: Settings | None = None):
    """返回已 compile 的图（可 invoke）。

    流程: START → policy → reason → [tool_exec] → retrieve → gate → grader
              → [rewrite loop] → draft → hallucination → finalize → END
    """
    settings = settings or get_settings()
    if getattr(settings, "agent_multi_agent_enabled", False) or (
        getattr(settings, "agent_graph_mode", "linear") == "multi"
    ):
        from app.agent_graph.multi_graph import build_multi_ticket_agent_graph

        return build_multi_ticket_agent_graph(settings=settings)

    def _policy(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_policy(s, settings=settings)

    def _reason(s: TicketAgentState) -> dict[str, Any]:
        return nodes.node_reason(s, settings=settings)

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
    g.add_node("policy", _policy)
    g.add_node("reason", _reason)
    g.add_node("retrieve", _retrieve)
    g.add_node("gate", _gate)
    g.add_node("grader", _grader)
    g.add_node("rewrite_query", _rewrite)
    g.add_node("draft", _draft)
    g.add_node("hallucination", _hallucination)
    g.add_node("finalize", nodes.node_finalize)

    # EcomAgent: add exchange parallel node
    # EcomAgent: Supervisor-Worker nodes
    from app.agent_graph.nodes import (
        node_exchange_parallel,
        node_refund_flow,
        node_complaint_flow,
        node_tracking_flow,
    )
    from app.supervisor.router import route_after_supervisor
    g.add_node("exchange_parallel", node_exchange_parallel)
    g.add_node("refund_flow",       node_refund_flow)
    g.add_node("complaint_flow",    node_complaint_flow)
    g.add_node("tracking_flow",     node_tracking_flow)

    # Edges
    g.add_edge(START, "policy")
    g.add_conditional_edges("policy", nodes.route_after_policy, {
        "retrieve": "reason",
        "finalize": "finalize",
    })
    # Supervisor routes to 4 intent-specific worker nodes + retrieve fallback
    g.add_conditional_edges("reason", route_after_supervisor, {
        "exchange_parallel": "exchange_parallel",
        "refund_flow":       "refund_flow",
        "complaint_flow":    "complaint_flow",
        "tracking_flow":     "tracking_flow",
        "retrieve":          "retrieve",
    })
    # All worker nodes go directly to draft (skip retrieve/gate/grader pipeline)
    g.add_edge("exchange_parallel", "draft")
    g.add_edge("refund_flow",       "draft")
    g.add_edge("complaint_flow",    "draft")
    g.add_edge("tracking_flow",     "draft")
    g.add_edge("retrieve", "gate")
    g.add_conditional_edges("gate", nodes.route_after_gate, {
        "grader": "grader",
        "finalize": "finalize",
    })
    g.add_conditional_edges("grader", nodes.route_after_grader, {
        "draft": "draft",
        "rewrite_query": "rewrite_query",
        "finalize": "finalize",
    })
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("draft", "hallucination")
    g.add_conditional_edges("hallucination", nodes.route_after_hallucination, {
        "finalize": "finalize",
    })
    g.add_edge("finalize", END)
    return g.compile()


def _ticket_agent_initial(
    *,
    ticket_id: str,
    user_query: str,
    user_context: dict[str, Any] | None = None,
    trace_id: str | None = None,
    top_k: int = 5,
    customer_id: str | None = None,
    customer_tier: str | None = None,
    session_id: str | None = None,
    conversation_history: str | None = None,
) -> TicketAgentState:
    return {
        "ticket_id": ticket_id,
        "user_query": user_query,
        "user_context": user_context or {},
        "trace_id": trace_id,
        "top_k": top_k,
        "customer_id": customer_id,
        "customer_tier": customer_tier,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "audit_trace": [],
        "human_review_required": False,
        "gate_passed": True,
        "iterations": 0,
        "max_iterations": nodes.MAX_AGENT_ITERATIONS,
        "rewrite_history": [],
        "loop_detected": False,
        "tool_calls": [],
        "tool_results": [],
        "_transition_count": 0,
        "_llm_failures": 0,
    }


def state_to_ticket_response_dict(
    state: TicketAgentState,
    *,
    ticket_id: str,
    user_query: str,
    trace_id: str | None,
) -> dict[str, Any]:
    """将图终态转为 TicketAgentResponse 字段字典。"""
    return {
        "ticket_id": ticket_id,
        "user_query": user_query,
        "final_action": str(state.get("final_action") or "unknown"),
        "human_review_required": bool(state.get("human_review_required")),
        "draft_reply": state.get("draft_reply"),
        "ticket_note": state.get("ticket_note"),
        "retrieval_query": state.get("retrieval_query"),
        "routed_domains": list(state.get("routed_domains") or []),
        "retrieved_chunks": list(state.get("retrieved_chunks") or []),
        "gate_passed": state.get("gate_passed"),
        "gate_error_code": state.get("gate_error_code"),
        "router_trace": state.get("router_trace"),
        "policy_result": state.get("policy_result"),
        "tool_calls": state.get("tool_calls"),
        "tool_results": state.get("tool_results"),
        "audit_trace": list(state.get("audit_trace") or []),
        "trace_id": trace_id,
    }


async def iter_ticket_agent_sse(
    *,
    ticket_id: str,
    user_query: str,
    user_context: dict[str, Any] | None = None,
    trace_id: str | None = None,
    top_k: int = 5,
    customer_id: str | None = None,
    customer_tier: str | None = None,
    session_id: str | None = None,
    conversation_history: str | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """按 LangGraph 节点更新 yield (event_type, payload)，支持 async 节点。"""
    graph = build_ticket_agent_graph(settings=settings)
    initial = _ticket_agent_initial(
        ticket_id=ticket_id,
        user_query=user_query,
        user_context=user_context,
        trace_id=trace_id,
        top_k=top_k,
        customer_id=customer_id,
        customer_tier=customer_tier,
        session_id=session_id,
        conversation_history=conversation_history,
    )
    final_state: TicketAgentState = dict(initial)
    seen_steps = 0
    async for chunk in graph.astream(initial, stream_mode="updates"):
        for _node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            final_state.update(update)
            trace = list(update.get("audit_trace") or final_state.get("audit_trace") or [])
            while seen_steps < len(trace):
                yield ("step", trace[seen_steps])
                seen_steps += 1
            draft = update.get("draft_reply")
            if draft and isinstance(draft, str):
                prev = final_state.get("_streamed_draft") or ""
                if len(draft) > len(prev):
                    yield ("token", {"text": draft[len(prev):]})
                    final_state["_streamed_draft"] = draft
    yield (
        "done",
        state_to_ticket_response_dict(
            final_state,
            ticket_id=ticket_id,
            user_query=user_query,
            trace_id=trace_id,
        ),
    )



async def run_ticket_agent(
    *,
    ticket_id: str,
    user_query: str,
    user_context: dict[str, Any] | None = None,
    trace_id: str | None = None,
    top_k: int = 5,
    customer_id: str | None = None,
    customer_tier: str | None = None,
    session_id: str | None = None,
    conversation_history: str | None = None,
    settings: Settings | None = None,
) -> TicketAgentState:
    settings = settings or get_settings()
    from app.telemetry import trace_span, setup_telemetry
    setup_telemetry(settings)
    with trace_span("run_ticket_agent", ticket_id=ticket_id, trace_id=trace_id or ""):
        recursion_limit = getattr(settings, "agent_graph_recursion_limit", 20)
        graph = build_ticket_agent_graph(settings=settings)
        initial = _ticket_agent_initial(
            ticket_id=ticket_id,
            user_query=user_query,
            user_context=user_context,
            trace_id=trace_id,
            top_k=top_k,
            customer_id=customer_id,
            customer_tier=customer_tier,
            session_id=session_id,
            conversation_history=conversation_history,
        )
        return await graph.ainvoke(initial, {"recursion_limit": recursion_limit})
