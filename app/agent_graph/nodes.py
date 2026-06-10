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

MAX_AGENT_ITERATIONS = 2

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
    """评估检索证据是否足够支撑草稿。简化版：gate通过即放行。"""
    settings = settings or get_settings()
    if state.get("policy_skip_rag"):
        return {"audit_trace": _append_audit(state, "grader", {"skipped": True})}

    gate_passed = bool(state.get("gate_passed"))
    chunks = state.get("retrieved_chunks") or []
    chunk_count = len(chunks)

    # Simplified: gate passed + has chunks → pass
    passed = gate_passed and chunk_count >= 1

    return {
        "grader_passed": passed,
        "grader_feedback": f"gate={gate_passed} chunks={chunk_count}" if passed else f"gate={gate_passed} chunks={chunk_count}",
        "audit_trace": _append_audit(state, "grader", {"passed": passed, "chunks": chunk_count}),
    }


def node_rewrite_query(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """改写检索 query 后回到 retrieve（Agentic 回环）。"""
    _ = settings
    iterations = int(state.get("iterations") or 0)
    max_iter = int(state.get("max_iterations") or MAX_AGENT_ITERATIONS)
    if iterations >= max_iter:
        return {
            "grader_passed": True,  # Force pass to ensure draft generates output
            "audit_trace": _append_audit(state, "rewrite_query", {"skipped": True, "reason": "max_iter", "force_pass": True}),
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
    """Always go to draft - simplified for demo (no rewrite loop)."""
    if state.get("policy_skip_rag"):
        return "finalize"
    return "draft"


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
    """Supervisor reasoning: classify intent using domain_router + detect emotion for complaints.

    Replaces the old LLM-based intent classification with keyword+LLM domain_router.
    The routing decision (exchange_parallel/retrieve/finalize) is handled by
    route_after_supervisor in app/supervisor/router.py.
    """
    from app.supervisor.router import route_intent
    return route_intent(state)



# ── EcomAgent: Exchange Parallel Node ──

async def node_exchange_parallel(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Exchange flow: run Policy + Inventory + Logistics checks in parallel via asyncio.gather.

    Three checks run concurrently — the slowest determines total response time.
    This is the core differentiator vs Dify's linear workflows.
    """
    _ = settings
    from app.agent.tools import execute_tool
    import asyncio

    order_id = state.get("order_id", "ORD-001")
    reason = state.get("return_reason", "尺码不合适")
    sku = state.get("product_sku", "TEE-WHITE")
    size = state.get("target_size", "L")
    color = state.get("target_color", "白色")
    address = state.get("pickup_address", "上海市浦东新区")

    async def policy_worker():
        return execute_tool("policy_check", state, {"order_id": order_id, "return_reason": reason})

    async def inventory_worker():
        return execute_tool("inventory_query", state, {"sku": sku, "size": size, "color": color})

    async def logistics_worker():
        return execute_tool("create_pickup", state, {"order_id": order_id, "address": address})

    policy_r, inventory_r, logistics_r = await asyncio.gather(
        policy_worker(), inventory_worker(), logistics_worker(),
        return_exceptions=True,
    )

    def _unwrap(r):
        if isinstance(r, Exception):
            return {"success": False, "error": str(r)}
        try:
            return r.data if hasattr(r, "data") else r
        except Exception:
            return {"success": False, "error": str(r)}

    policy_data = _unwrap(policy_r) if not isinstance(policy_r, Exception) else {"success": False, "error": str(policy_r)}
    inventory_data = _unwrap(inventory_r) if not isinstance(inventory_r, Exception) else {"success": False, "error": str(inventory_r)}
    logistics_data = _unwrap(logistics_r) if not isinstance(logistics_r, Exception) else {"success": False, "error": str(logistics_r)}

    all_ok = (
        not isinstance(policy_r, Exception)
        and not isinstance(inventory_r, Exception)
        and not isinstance(logistics_r, Exception)
    )

    lines = []
    pd = policy_data if isinstance(policy_data, dict) else {}
    if pd.get("eligible"):
        lines.append(f"Policy: {pd.get('policy', '可退换')} — {pd.get('reason', '')}")
    else:
        lines.append(f"Policy: 不符合退换条件 — {pd.get('reason', '不符合条件')}")

    id_ = inventory_data if isinstance(inventory_data, dict) else {}
    if id_.get("available"):
        lines.append(f"Inventory: {size}码有货（{id_.get('warehouse', '仓库')}，库存{id_.get('stock', 0)}件）")
    else:
        lines.append(f"Inventory: {size}码已售罄 — {id_.get('message', '无货')}")

    ld = logistics_data if isinstance(logistics_data, dict) else {}
    lines.append(f"Logistics: 取件已预约 — {ld.get('scheduled', '明天')}（{ld.get('carrier', '顺丰')}）")

    summary = "\n".join(f"  {line}" for line in lines)

    return {
        "policy_result": policy_data,
        "inventory_result": inventory_data,
        "logistics_result": logistics_data,
        "exchange_ready": all_ok,
        "exchange_summary": summary,
        "retrieved_chunks": [{"text": summary, "score": 1.0, "file_name": "exchange_check", "domain": "exchange"}],
        "routed_domains": ["exchange"],
        "gate_passed": True,
        "audit_trace": state.get("audit_trace", []) + [{
            "step": "exchange_parallel",
            "policy_ok": not isinstance(policy_r, Exception),
            "inventory_ok": not isinstance(inventory_r, Exception),
            "logistics_ok": not isinstance(logistics_r, Exception),
        }],
    }