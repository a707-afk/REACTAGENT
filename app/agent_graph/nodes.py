"""LangGraph 节点：串联 policy / retrieve / gate / draft。"""
from __future__ import annotations

import logging
from typing import Any

from app.agent_graph.state import TicketAgentState
from app.citation_verify import sentence_level_grounding
from app.config import Settings, get_settings
from app.policy.engine import evaluate_policy
from app.policy.models import PolicyAction
from app.retrieval_gates import evaluate_similarity_gate
from app.retrieval_pipeline import retrieve_scored_nodes
from app.schemas import UserContext
from app.vector_index import get_vector_index

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 3

_CHAT_SYSTEM = (
    "你是企业内部工单助手。仅依据提供的知识片段作答，使用简体中文，条理清晰。"
)


def _append_audit(state: TicketAgentState, step: str, detail: dict[str, Any]) -> list[dict[str, Any]]:
    trace = list(state.get("audit_trace") or [])
    trace.append({"step": step, **detail})
    return trace


def _user_context_from_state(state: TicketAgentState) -> UserContext | None:
    raw = state.get("user_context")
    if not raw:
        return None
    return UserContext.model_validate(raw)


def _policy_summary_dict(pe) -> dict[str, Any]:
    pa = pe.policy_action
    if isinstance(pa, PolicyAction):
        pa_s = pa.value
    else:
        pa_s = str(pa) if pa is not None else None
    return {
        "should_skip_rag": pe.should_skip_rag,
        "policy_action": pa_s,
        "policy_risk_level": pe.policy_risk_level,
        "intercept_reason_code": pe.intercept_reason_code,
        "requires_human_review": pe.requires_human_review,
        "policy_warnings": list(pe.policy_warnings),
    }


def node_policy(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    q = (state.get("user_query") or "").strip()
    uc = _user_context_from_state(state)
    pe = evaluate_policy(
        q,
        settings,
        trace_id=state.get("trace_id"),
        user_context_summary=(
            {
                "tenant_id": uc.tenant_id,
                "roles": list(uc.roles or []),
                "security_clearance": uc.security_clearance,
            }
            if uc
            else None
        ),
        endpoint="agent_ticket",
    )
    risk = pe.policy_risk_level or ("high" if pe.should_skip_rag else "low")
    out: dict[str, Any] = {
        "policy_skip_rag": pe.should_skip_rag,
        "policy_result": _policy_summary_dict(pe),
        "risk_level": risk,
        "human_review_required": pe.requires_human_review or pe.should_skip_rag,
        "audit_trace": _append_audit(
            state,
            "policy",
            {"skip_rag": pe.should_skip_rag, "action": _policy_summary_dict(pe).get("policy_action")},
        ),
    }
    if pe.should_skip_rag:
        out["final_action"] = "policy_intercept"
        out["draft_reply"] = pe.message_zh or settings.refusal_gate_fail
        out["ticket_note"] = f"策略拦截: {pe.intercept_reason_code or 'POLICY_HIT'}"
    return out


def node_retrieve(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if state.get("policy_skip_rag"):
        return {
            "retrieved_chunks": [],
            "audit_trace": _append_audit(state, "retrieve", {"skipped": True}),
        }
    q = (state.get("retrieval_query") or state.get("user_query") or "").strip()
    uc = _user_context_from_state(state)
    top_k = int(state.get("top_k") or 5)
    index = get_vector_index()
    sr = retrieve_scored_nodes(
        index,
        q,
        top_k,
        settings,
        user_context=uc,
        skip_domain_router=False,
        trace_id=state.get("trace_id"),
    )
    chunks: list[dict[str, Any]] = []
    for sn in sr.nodes:
        meta = dict(sn.node.metadata or {})
        chunks.append(
            {
                "text": sn.node.get_content(),
                "score": float(sn.score) if sn.score is not None else None,
                "file_path": meta.get("file_path"),
                "file_name": meta.get("file_name"),
                "domain": meta.get("domain"),
                "node_id": sn.node.node_id,
            }
        )
    domains: list[str] = []
    if sr.router_result and sr.router_result.allowed_domains:
        domains = list(sr.router_result.allowed_domains)
    rt = None
    if sr.router_result:
        rt = {
            "allowed_domains": domains,
            "primary_domain": sr.router_result.primary_domain,
            "confidence": sr.router_result.confidence,
            "method": sr.router_result.method,
        }
    return {
        "retrieval_query": sr.retrieval_query,
        "retrieved_chunks": chunks,
        "routed_domains": domains,
        "router_trace": rt,
        "audit_trace": _append_audit(
            state,
            "retrieve",
            {"hits": len(chunks), "primary_domain": (rt or {}).get("primary_domain")},
        ),
    }


def node_evidence_gate(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if state.get("policy_skip_rag"):
        return {"audit_trace": _append_audit(state, "gate", {"skipped": True})}

    from llama_index.core.schema import NodeWithScore, TextNode

    scored: list[NodeWithScore] = []
    for c in state.get("retrieved_chunks") or []:
        node = TextNode(
            text=str(c.get("text") or ""),
            metadata={
                "file_path": c.get("file_path"),
                "file_name": c.get("file_name"),
                "domain": c.get("domain"),
            },
            id_=str(c.get("node_id") or ""),
        )
        sc = c.get("score")
        scored.append(
            NodeWithScore(node=node, score=float(sc) if sc is not None else None)
        )

    if not scored:
        return {
            "gate_passed": False,
            "gate_error_code": "NO_RESULTS",
            "human_review_required": True,
            "final_action": "no_evidence",
            "draft_reply": settings.refusal_no_results,
            "ticket_note": "检索无命中，需人工处理",
            "audit_trace": _append_audit(state, "gate", {"passed": False, "code": "NO_RESULTS"}),
        }

    gate = evaluate_similarity_gate(scored, settings, trace_id=state.get("trace_id"))
    out: dict[str, Any] = {
        "gate_passed": gate.passed,
        "gate_error_code": gate.error_code,
        "ranked_quality_scores": gate.ranked_scores,
        "audit_trace": _append_audit(
            state,
            "gate",
            {"passed": gate.passed, "code": gate.error_code, "best": gate.ranked_scores[:1]},
        ),
    }
    if not gate.passed:
        out["human_review_required"] = True
        out["final_action"] = "gate_fail"
        out["draft_reply"] = settings.refusal_gate_fail
        out["ticket_note"] = f"证据门控未通过: {gate.error_code}"
    elif state.get("risk_level") == "high" or state.get("policy_result", {}).get(
        "requires_human_review"
    ):
        out["human_review_required"] = True
    return out


def node_draft(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Generate draft reply with LLM circuit breaker protection."""
    settings = settings or get_settings()
    if state.get("policy_skip_rag") or not state.get("gate_passed") or not state.get("grader_passed"):
        return {"audit_trace": _append_audit(state, "draft", {"skipped": True})}

    from app.agent_graph.fault_tolerance import check_circuit_breaker, record_llm_failure, record_llm_success

    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        return {
            "draft_reply": settings.refusal_no_results,
            "human_review_required": True,
            "audit_trace": _append_audit(state, "draft", {"skipped": True, "reason": "no_chunks"}),
        }

    # Build prompt from top chunks
    parts: list[str] = []
    for i, c in enumerate(chunks[:5]):
        parts.append(
            f"[{i + 1}] {c.get('file_name') or ''} ({c.get('file_path') or ''})\n{c.get('text') or ''}\n"
        )
    user_prompt = (
        f"工单问题：{state.get('user_query')}\n\n"
        f"知识片段：\n{''.join(parts)}\n"
        "请给出建议回复要点（条列即可）。"
    )

    # Circuit breaker: if LLM already failed 3 times, skip and use fallback
    if check_circuit_breaker(state):
        logger.warning("draft: LLM circuit breaker open, using fallback")
        top = chunks[0]
        draft = (
            "【自动回复 — LLM 暂不可用】\n"
            f"相关知识：{top.get('file_name') or '未知'}\n"
            f"{(top.get('text') or '')[:500]}"
        )
        return {
            "draft_reply": draft,
            "human_review_required": True,
            "ticket_note": "LLM circuit breaker open",
            "audit_trace": _append_audit(state, "draft", {"chars": len(draft), "fallback": "circuit_breaker"}),
        }

    draft: str
    try:
        from app.llm_zhipu import chat_completion
        draft = chat_completion(_CHAT_SYSTEM, user_prompt)
        state["_llm_failures"] = record_llm_success(state)
    except Exception as e:
        state["_llm_failures"] = record_llm_failure(state)
        logger.warning("draft LLM 不可用 (failures=%s): %s", state.get("_llm_failures", 0), e)
        top = chunks[0] if chunks else {}
        draft = (
            "【自动回复 — LLM 调用失败】\n"
            f"最相关片段来自 {top.get('file_name') or '未知'}：\n"
            f"{(top.get('text') or '')[:600]}\n\n"
            "如需进一步帮助，请回复「转人工」。"
        )

    return {
        "draft_reply": draft,
        "human_review_required": state.get("_llm_failures", 0) > 0,
        "audit_trace": _append_audit(state, "draft", {"chars": len(draft), "llm_failures": state.get("_llm_failures", 0)}),
    }


def node_grader(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """评估检索证据是否足够支撑草稿（启发式；TODO: 可换 LLM grader）。"""
    settings = settings or get_settings()
    if state.get("policy_skip_rag"):
        return {"audit_trace": _append_audit(state, "grader", {"skipped": True})}

    try:
        chunks = state.get("retrieved_chunks") or []
        gate_passed = bool(state.get("gate_passed"))
        scores = list(state.get("ranked_quality_scores") or [])
        best = float(scores[0]) if scores else 0.0
        chunk_count = len(chunks)

        # 启发式：门控通过 + 至少 1 条 chunk + 最优分不低于阈值 90%
        thr = float(settings.retrieval_similarity_threshold)
        score_ok = best >= thr * 0.9 if scores else False
        passed = gate_passed and chunk_count >= 1 and score_ok

        if not chunks:
            feedback = "无检索片段"
        elif not gate_passed:
            feedback = f"证据门控未通过: {state.get('gate_error_code') or 'unknown'}"
        elif chunk_count < 1:
            feedback = "chunk 数量不足"
        elif not score_ok:
            feedback = f"最优分 {best:.3f} 低于阈值 {thr:.3f}"
        else:
            feedback = f"证据充分（{chunk_count} 条，best={best:.3f}）"

        return {
            "grader_passed": passed,
            "grader_feedback": feedback,
            "audit_trace": _append_audit(
                state,
                "grader",
                {"passed": passed, "chunks": chunk_count, "best": best, "feedback": feedback},
            ),
        }
    except Exception as e:
        logger.warning("grader 异常，降级为不通过: %s", e)
        return {
            "grader_passed": False,
            "grader_feedback": f"grader 异常: {e}",
            "human_review_required": True,
            "audit_trace": _append_audit(state, "grader", {"passed": False, "error": str(e)}),
        }


def node_rewrite_query(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """改写检索 query 后回到 retrieve（Agentic 回环）。"""
    _ = settings
    iterations = int(state.get("iterations") or 0)
    max_iter = int(state.get("max_iterations") or MAX_AGENT_ITERATIONS)
    if iterations >= max_iter:
        return {
            "grader_passed": False,
            "audit_trace": _append_audit(state, "rewrite_query", {"skipped": True, "reason": "max_iter"}),
        }

    original = (state.get("user_query") or "").strip()
    history = list(state.get("rewrite_history") or [])

    # 按轮次追加检索提示词
    suffixes = [" 详细说明", " 相关政策流程", " 标准操作步骤"]
    suffix = suffixes[min(iterations, len(suffixes) - 1)]
    new_query = f"{original}{suffix}".strip()
    action_sig = f"rewrite:{new_query}"

    if action_sig in history:
        return {
            "loop_detected": True,
            "grader_passed": False,
            "grader_feedback": "检测到相同改写循环，停止重试",
            "human_review_required": True,
            "audit_trace": _append_audit(
                state,
                "rewrite_query",
                {"loop_detected": True, "query": new_query},
            ),
        }

    history.append(action_sig)
    return {
        "iterations": iterations + 1,
        "retrieval_query": new_query,
        "rewrite_history": history,
        "grader_passed": False,
        "audit_trace": _append_audit(
            state,
            "rewrite_query",
            {"iteration": iterations + 1, "query": new_query},
        ),
    }


def node_hallucination(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    from app.telemetry import trace_span
    with trace_span("node_hallucination", ticket_id=state.get("ticket_id", "")[:32]):
        """草稿句级 grounding：调用 citation_verify.sentence_level_grounding。"""
    _ = settings
    if state.get("policy_skip_rag") or not state.get("grader_passed"):
        return {"audit_trace": _append_audit(state, "hallucination", {"skipped": True})}

    try:
        draft = (state.get("draft_reply") or "").strip()
        chunks = list(state.get("retrieved_chunks") or [])
        citations = [
            {
                "index": i + 1,
                "file_name": c.get("file_name"),
                "file_path": c.get("file_path"),
                "node_id": c.get("node_id"),
            }
            for i, c in enumerate(chunks[:5])
        ]

        if not draft:
            return {
                "hallucination_passed": False,
                "hallucination_feedback": "草稿为空",
                "citations": citations,
                "human_review_required": True,
                "audit_trace": _append_audit(state, "hallucination", {"passed": False, "reason": "empty_draft"}),
            }

        report = sentence_level_grounding(draft, chunks, prefer_embedding=False)
        passed = bool(report.passed)
        feedback = report.feedback or ("grounding_ok" if passed else "grounding_fail")

        out: dict[str, Any] = {
            "hallucination_passed": passed,
            "hallucination_feedback": feedback,
            "citations": citations,
            "audit_trace": _append_audit(
                state,
                "hallucination",
                {
                    "passed": passed,
                    "method": report.method,
                    "overlap_ratio": round(report.overlap_ratio, 4),
                    "unsupported_sentence_rate": round(report.unsupported_sentence_rate, 4),
                    "citations": len(citations),
                },
            ),
        }
        if not passed:
            out["human_review_required"] = True
            out["ticket_note"] = "幻觉检测未通过，需人工复核草稿"
            # Grounding strip: remove unsupported sentences for human review
            try:
                from app.citation_verify import strip_unsupported_sentences
                ctx = "\n".join(c.get("text", "") for c in chunks)
                stripped = strip_unsupported_sentences(draft, ctx)
                if stripped != draft:
                    out["draft_reply"] = stripped
            except Exception:
                pass
        return out
    except Exception as e:
        logger.warning("hallucination 检测异常，降级放行并标记人工: %s", e)
        return {
            "hallucination_passed": True,
            "hallucination_feedback": f"检测异常降级: {e}",
            "human_review_required": True,
            "audit_trace": _append_audit(state, "hallucination", {"passed": True, "degraded": True}),
        }


def node_finalize(state: TicketAgentState) -> dict[str, Any]:
    if state.get("final_action"):
        note = state.get("ticket_note") or state.get("final_action")
        return {
            "ticket_note": note,
            "audit_trace": _append_audit(state, "finalize", {"action": state.get("final_action")}),
        }

    human = bool(state.get("human_review_required"))
    action = "await_human_review" if human else "draft_ready"
    note = (
        "已生成草稿，等待二线审核后发送。"
        if human
        else "已生成建议回复，可经客服确认后发送。"
    )
    return {
        "final_action": action,
        "human_review_required": human,
        "ticket_note": note,
        "audit_trace": _append_audit(state, "finalize", {"action": action, "human": human}),
    }


def route_after_policy(state: TicketAgentState) -> str:
    return "finalize" if state.get("policy_skip_rag") else "retrieve"


def route_after_gate(state: TicketAgentState) -> str:
    """gate_passed=False 或已 final_action 时直接 finalize，否则 grader。"""
    if state.get("policy_skip_rag"):
        return "finalize"
    if not state.get("gate_passed", True):
        return "finalize"
    if state.get("final_action"):
        return "finalize"
    return "grader"


def route_after_grader(state: TicketAgentState) -> str:
    if state.get("policy_skip_rag"):
        return "finalize"
    if state.get("loop_detected"):
        return "finalize"
    if state.get("grader_passed"):
        return "draft"
    iterations = int(state.get("iterations") or 0)
    max_iter = int(state.get("max_iterations") or MAX_AGENT_ITERATIONS)
    if iterations < max_iter:
        return "rewrite_query"
    return "finalize"


def route_after_hallucination(state: TicketAgentState) -> str:
    """Grounding 失败→ draft 重试（上限 agent_max_draft_attempts）。"""
    if state.get("final_action"):
        return "finalize"
    passed = state.get("hallucination_passed", True)
    if passed is False:
        from app.config import get_settings
        s = get_settings()
        max_drafts = getattr(s, "agent_max_draft_attempts", 2)
        if state.get("draft_attempts", 0) < max_drafts:
            return "draft"
    return "finalize"


# ── Agent Tool Reasoning Nodes (Phase: tools integration) ──

REASON_SYSTEM = (
    "你是企业客服 AI Agent。分析用户问题，决定下一步行动。"
    "输出严格 JSON：{\"action\": \"retrieve|create_ticket|escalate|direct_answer\", \"reason\": \"...\", \"tool_args\": {...}}"
)


def node_reason(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Agent reasoning: classify intent and decide which tools to call."""
    settings = settings or get_settings()
    from app.agent_graph.fault_tolerance import check_circuit_breaker, record_llm_failure, record_llm_success
    q = (state.get("user_query") or "").strip()
    if state.get("policy_skip_rag"):
        return {"audit_trace": _append_audit(state, "reason", {"skipped": True})}

    # Heuristic pre-filter: fast pattern matching before LLM call
    q_lower = q.lower()
    escalate_keywords = ["人工", "转人工", "找经理", "投诉", "投诉你们", "叫你们领导", "human agent", "speak to manager", "supervisor"]
    ticket_keywords = ["建工单", "创建工单", "提交工单", "上报", "create ticket", "open ticket", "file a ticket"]

    history = state.get("conversation_history") or ""

    for kw in escalate_keywords:
        if kw in q_lower:
            return {
                "tool_calls": [{"name": "escalate", "args": {"reason": q[:200], "urgency": "immediate"}}],
                "audit_trace": _append_audit(state, "reason", {"method": "heuristic", "action": "escalate"}),
            }

    for kw in ticket_keywords:
        if kw in q_lower:
            return {
                "tool_calls": [{"name": "create_ticket", "args": {"title": q[:200], "description": q, "priority": "p2_medium"}}],
                "audit_trace": _append_audit(state, "reason", {"method": "heuristic", "action": "create_ticket"}),
            }

    # Try LLM-based reasoning if API key is configured and circuit not open
    if check_circuit_breaker(state):
        logger.debug("reason: LLM circuit breaker open, skipping LLM call")
        return {
            "tool_calls": [],
            "audit_trace": _append_audit(state, "reason", {"method": "default", "action": "retrieve", "circuit_open": True}),
        }

    try:
        from app.llm_zhipu import chat_completion

        user_prompt = (
            f"对话历史：{history or '无'}\n"
            f"用户问题：{q}\n"
            "可用的工具：retrieve_kb（搜索知识库）、create_ticket（建工单）、escalate（转人工）。"
        )
        raw = chat_completion(REASON_SYSTEM, user_prompt)
        import json, re
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            obj = json.loads(m.group())
            action = obj.get("action", "retrieve")
            tool_name = None
            if action == "escalate":
                tool_name = "escalate"
            elif action == "create_ticket":
                tool_name = "create_ticket"
            elif action == "retrieve":
                tool_name = "retrieve_kb"

            tool_args = obj.get("tool_args", {})
            if not isinstance(tool_args, dict):
                tool_args = {}
            if tool_name and tool_name != "retrieve_kb":
                return {
                    "tool_calls": [{"name": tool_name, "args": tool_args}],
                    "audit_trace": _append_audit(state, "reason", {"method": "llm", "action": action}),
                }
    except Exception as e:
        state["_llm_failures"] = record_llm_failure(state)
        logger.debug("reason LLM fallback (failures=%s): %s", state.get("_llm_failures", 0), e)

    # Default: retrieve knowledge base
    return {
        "tool_calls": [],
        "audit_trace": _append_audit(state, "reason", {"method": "default", "action": "retrieve"}),
    }


def node_tool_exec(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Execute tool calls decided by the reasoning node."""
    _ = settings
    tool_calls = list(state.get("tool_calls") or [])
    if not tool_calls:
        return {"audit_trace": _append_audit(state, "tool_exec", {"skipped": True})}

    from app.agent.tools import execute_tool

    results: list[dict[str, Any]] = []
    escalated = False
    ticket_created = False

    for tc in tool_calls:
        name = str(tc.get("name", ""))
        args = dict(tc.get("args", {}))
        tr = execute_tool(name, state, args)
        results.append({"name": name, "success": tr.success, "data": tr.data, "error": tr.error})
        if name == "escalate" and tr.success:
            escalated = True
        if name == "create_ticket" and tr.success:
            ticket_created = True

    out: dict[str, Any] = {
        "tool_results": results,
        "audit_trace": _append_audit(state, "tool_exec", {
            "calls": len(tool_calls), "ok": sum(1 for r in results if r["success"])
        }),
    }

    if escalated:
        out["final_action"] = "escalated"
        out["human_review_required"] = True
        out["ticket_note"] = "已转人工二线处理"
        out["draft_reply"] = "已为您转接人工客服，请稍候。"
    elif ticket_created:
        out["final_action"] = "ticket_created"
        out["ticket_note"] = "已创建工单"

    return out


def route_after_reason(state: TicketAgentState) -> str:
    """After reasoning: go to tool_exec if tool calls exist, otherwise retrieve."""
    if state.get("policy_skip_rag"):
        return "finalize"
    tool_calls = state.get("tool_calls") or []
    non_retrieve = [tc for tc in tool_calls if tc.get("name") != "retrieve_kb"]
    if non_retrieve:
        return "tool_exec"
    return "retrieve"


def route_after_tool_exec(state: TicketAgentState) -> str:
    """After tool execution: if escalated/ticketed, finalize; otherwise retrieve."""
    if state.get("final_action") in ("escalated", "ticket_created"):
        return "finalize"
    # Still need to search knowledge base
    return "retrieve"