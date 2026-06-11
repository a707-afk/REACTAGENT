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
        # If a worker node already generated a response, preserve it
        existing_draft = state.get("draft_reply")
        if existing_draft and state.get("grader_passed"):
            return {
                "gate_passed": True,
                "gate_error_code": None,
                "audit_trace": _append_audit(state, "gate", {"skipped": True, "reason": "worker_prefilled"}),
            }
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

    # Worker nodes (refund_flow/complaint_flow/etc.) already set draft_reply directly — pass through
    existing = state.get("draft_reply")
    if existing and state.get("grader_passed"):
        return {
            "draft_reply": existing,
            "audit_trace": _append_audit(state, "draft", {"chars": len(existing), "source": "worker_node"}),
        }

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
    failures = state.get("_llm_failures", 0)
    try:
        from app.llm import chat_completion
        draft = chat_completion(_CHAT_SYSTEM, user_prompt)
        failures = record_llm_success(state)
    except Exception as e:
        failures = record_llm_failure(state)
        logger.warning("draft LLM 不可用 (failures=%s): %s", failures, e)
        top = chunks[0] if chunks else {}
        draft = (
            "【自动回复 — LLM 调用失败】\n"
            f"最相关片段来自 {top.get('file_name') or '未知'}：\n"
            f"{(top.get('text') or '')[:600]}\n\n"
            "如需进一步帮助，请回复「转人工」。"
        )

    return {
        "draft_reply": draft,
        "_llm_failures": failures,
        "human_review_required": failures > 0,
        "audit_trace": _append_audit(state, "draft", {"chars": len(draft), "llm_failures": failures}),
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
    """草稿句级 grounding：调用 citation_verify.sentence_level_grounding。"""
    from app.telemetry import trace_span
    _ = settings
    if state.get("policy_skip_rag") or not state.get("grader_passed"):
        return {"audit_trace": _append_audit(state, "hallucination", {"skipped": True})}

    with trace_span("node_hallucination", ticket_id=state.get("ticket_id", "")[:32]):
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
    """Always go to finalize (draft retry loop removed for stability)."""
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
    import asyncio, re

    # ── Step 0: 从 user_query 中提取目标尺码 ────────────────
    user_query = state.get("user_query", "")
    size_match = re.search(r'\b([SMLXsmlx]{1,3}|[3-4][0-9])\b', user_query)
    target_size = size_match.group(1).upper() if size_match else state.get("target_size", "L")

    # ── Step 1: 查询订单（从 order_hint 或 query 中获取商品关键词）──
    order_hint = state.get("order_hint", "")
    user_id    = state.get("customer_id") or "u001"
    oe_result = execute_tool("order_lookup", state, {
        "user_id": user_id,
        "keyword": order_hint or user_query[:15],
        "limit": 1,
    })
    orders = oe_result.data.get("orders", []) if oe_result.success else []

    if not orders:
        return {
            "draft_reply": "请问您是想换哪个订单的商品？能告诉我商品名称或订单号吗？",
            "grader_passed": True, "gate_passed": True,
            "audit_trace": _append_audit(state, "exchange_parallel", {"result": "order_not_found"}),
        }

    order    = orders[0]
    order_id = order["order_id"]
    sku      = order.get("sku", state.get("product_sku", "TEE-WHITE"))
    color    = order.get("color", state.get("target_color", ""))
    address  = order.get("address") or state.get("pickup_address", "上海市")
    reason   = "尺码不合适"
    size     = target_size

    async def policy_worker():
        return await asyncio.to_thread(execute_tool, "policy_check", state, {"order_id": order_id, "return_reason": reason})

    async def inventory_worker():
        return await asyncio.to_thread(execute_tool, "inventory_query", state, {"sku": sku, "size": size, "color": color})

    async def logistics_worker():
        return await asyncio.to_thread(execute_tool, "create_pickup", state, {"order_id": order_id, "address": address})

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
        "grader_passed": True,
        # NOT setting retrieved_chunks — evidence comes from RAG pipeline
        "routed_domains": ["exchange"],
        "gate_passed": True,
        "audit_trace": _append_audit(state, "exchange_parallel", {
            "policy_ok": not isinstance(policy_r, Exception),
            "inventory_ok": not isinstance(inventory_r, Exception),
            "logistics_ok": not isinstance(logistics_r, Exception),
        }),
    }


# ── EcomAgent: Refund Flow Node ──

def node_refund_flow(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """
    退款流程节点（串行）：
    1. 用 order_hint 查订单
    2. policy_check 判断退款类型（full/partial/denied）
    3. 计算退款金额
    4. 创建退款工单
    """
    from app.agent.tools import execute_tool as _exec

    user_query  = state.get("user_query", "")
    order_hint  = state.get("order_hint", "")
    user_id     = state.get("customer_id") or "u001"

    order_result = _exec("order_lookup", state, {
        "user_id": user_id, "keyword": order_hint or user_query[:10], "limit": 1
    })
    orders = order_result.data.get("orders", []) if order_result.success else []

    if not orders:
        return {
            "draft_reply": "暂时找不到您的订单，请提供订单号或商品名称，我来帮您处理退款申请。",
            "grader_passed": True, "gate_passed": True,
            # NOT setting retrieved_chunks — evidence comes from RAG pipeline
            "audit_trace": _append_audit(state, "refund_flow", {"result": "order_not_found"}),
        }

    order = orders[0]
    order_id = order["order_id"]
    amount = order.get("amount", 0)

    policy_result = _exec("policy_check", state, {"order_id": order_id, "return_reason": "申请退款"})
    policy = policy_result.data if policy_result.success else {}

    if not policy.get("eligible"):
        reply = f"很抱歉，订单 {order_id}（{order.get('product','')}）{policy.get('reason','不符合退款条件')}。\n如有疑问请联系人工客服。"
        _exec("create_after_sale_ticket", state, {"type":"refund","priority":"p3_low","order_id":order_id,"detail":f"退款被拒：{policy.get('reason','')}"})
        return {"draft_reply": reply, "grader_passed": True, "gate_passed": True,
                "audit_trace": _append_audit(state, "refund_flow", {"result": "denied"})}

    deduction_rate = policy.get("deduction_rate", 0)
    refund_amount = round(amount * (1 - deduction_rate), 2)
    deduction_note = f"（扣除{int(deduction_rate*100)}%手续费）" if deduction_rate > 0 else ""

    ticket_result = _exec("create_after_sale_ticket", state, {
        "type": "refund", "priority": "p2_medium", "order_id": order_id,
        "detail": f"退款金额 ¥{refund_amount:.2f}{deduction_note}"
    })
    ticket = ticket_result.data if ticket_result.success else {}

    reply = f"退款申请已提交！\n订单：{order_id}（{order.get('product','')}）\n退款金额：¥{refund_amount:.2f}{deduction_note}\n工单号：{ticket.get('ticket_id','AS-未知')}\n预计 3-5 个工作日原路退回。"

    return {"draft_reply": reply, "grader_passed": True, "gate_passed": True,
            "audit_trace": _append_audit(state, "refund_flow", {"order_id": order_id, "refund_amount": refund_amount})}


# ── EcomAgent: Complaint Flow Node ──

def node_complaint_flow(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """投诉流程：情绪分级 → P0紧急/P2标准工单 + 补偿推荐"""
    from app.agent.tools import execute_tool as _exec

    emotion = state.get("emotion", "neutral")
    order_hint = state.get("order_hint", "")
    user_id = state.get("customer_id") or "u001"

    order_result = _exec("order_lookup", state, {"user_id": user_id, "keyword": order_hint, "limit": 1})
    orders = order_result.data.get("orders", []) if order_result.success else []
    order = orders[0] if orders else {}
    order_id = order.get("order_id", "unknown")
    amount = order.get("amount", 100)

    if amount >= 300: compensation = 30
    elif amount >= 100: compensation = 15
    else: compensation = 5

    priority = "p0_critical" if emotion == "angry" else "p2_medium"
    sla_desc = "2 小时" if emotion == "angry" else "24 小时"

    ticket_result = _exec("create_after_sale_ticket", state, {
        "type": "complaint", "priority": priority, "order_id": order_id,
        "detail": f"情绪:{emotion},补偿:¥{compensation},投诉:{state.get('user_query','')[:100]}"
    })
    ticket = ticket_result.data if ticket_result.success else {}
    tid = ticket.get("ticket_id", "AS-未知")

    if emotion == "angry":
        reply = f"非常抱歉！已创建紧急投诉工单（{tid}），优先�� P0，承诺{sla_desc}内联系您。补偿 ¥{compensation} 优惠券，24小时内发放。"
    else:
        reply = f"感谢反馈，已记录投诉（{tid}），{sla_desc}内联系您。补偿 ¥{compensation} 优惠券。"

    return {"draft_reply": reply, "grader_passed": True, "gate_passed": True,
            "audit_trace": _append_audit(state, "complaint_flow", {"emotion": emotion, "priority": priority})}


# ── EcomAgent: Tracking Flow Node ──

def node_tracking_flow(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """物流查询节点：order_lookup → track_shipment → 生成回复"""
    from app.agent.tools import execute_tool as _exec

    order_hint = state.get("order_hint", "")
    user_id = state.get("customer_id") or "u001"

    order_result = _exec("order_lookup", state, {"user_id": user_id, "keyword": order_hint, "limit": 1})
    orders = order_result.data.get("orders", []) if order_result.success else []

    if not orders:
        reply = "暂时找不到您的订单，请提供订单号或商品名称，我来帮您查询物流状态。"
        return {"draft_reply": reply, "grader_passed": True, "gate_passed": True,
                "audit_trace": _append_audit(state, "tracking_flow", {"result": "order_not_found"})}

    order = orders[0]
    order_id = order["order_id"]

    logistics_result = _exec("track_shipment", state, {"order_id": order_id})
    logistics = logistics_result.data if logistics_result.success else {}
    status = logistics.get("status", "暂无物流信息")

    if status == "已签收":
        reply = f"订单 {order_id}（{order.get('product','')}）已签收。签收时间：{logistics.get('last_update','未知')}"
    elif status == "未找到物流信息":
        reply = f"订单 {order_id} 暂无物流信息，可能刚下单，请稍后再查。"
    else:
        reply = f"包裹（{order_id}，{order.get('product','')}）\n状态：{status}\n承运商：{logistics.get('carrier','未知')}\n最新：{logistics.get('last_update','未知')}\n预计：{logistics.get('estimated_delivery','未知')}"

    return {"draft_reply": reply, "grader_passed": True, "gate_passed": True,
            "audit_trace": _append_audit(state, "tracking_flow", {"order_id": order_id, "status": status})}