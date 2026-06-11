"""LangGraph 工单助手 API。"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent_graph.graph import iter_ticket_agent_sse, run_ticket_agent
from app.config import get_settings
from app.schemas import TicketAgentRequest, TicketAgentResponse
from app.sse import format_sse_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


def _ticket_response_from_result(
    req: TicketAgentRequest,
    result: dict[str, Any],
    tid: str | None,
) -> TicketAgentResponse:
    return TicketAgentResponse(
        ticket_id=req.ticket_id,
        user_query=req.user_query,
        final_action=str(result.get("final_action") or "unknown"),
        human_review_required=bool(result.get("human_review_required")),
        draft_reply=result.get("draft_reply"),
        ticket_note=result.get("ticket_note"),
        retrieval_query=result.get("retrieval_query"),
        routed_domains=list(result.get("routed_domains") or []),
        retrieved_chunks=list(result.get("retrieved_chunks") or []),
        gate_passed=result.get("gate_passed"),
        gate_error_code=result.get("gate_error_code"),
        router_trace=result.get("router_trace"),
        policy_result=result.get("policy_result"),
        audit_trace=list(result.get("audit_trace") or []),
        trace_id=tid,
    )


@router.post("/agent/ticket", response_model=TicketAgentResponse)
async def agent_ticket(req: TicketAgentRequest, request: Request) -> TicketAgentResponse:
    tid = getattr(request.state, "trace_id", None)
    settings = get_settings()

    # Harness unified mode: route /agent/ticket through Harness
    if getattr(settings, "agent_harness_unified", False):
        return await _agent_ticket_via_harness(req, settings, tid)

    # Shadow mode: run Harness in parallel for comparison (fire-and-forget)
    if getattr(settings, "agent_harness_shadow", False):
        asyncio.ensure_future(_run_harness_shadow(req, settings))

    # Default: LangGraph path
    timeout_s = getattr(settings, "api_agent_timeout_seconds", 120.0)
    try:
        uc_dict = req.user_context.model_dump() if req.user_context else {}
        result = await run_ticket_agent(
            ticket_id=req.ticket_id,
            user_query=req.user_query,
            user_context=uc_dict,
            trace_id=tid,
            top_k=req.top_k,
            customer_id=req.customer_id,
            customer_tier=req.customer_tier,
            session_id=req.session_id,
            settings=settings,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    logger.info(
        "%s",
        json.dumps(
            {
                "trace_id": tid,
                "event": "agent_ticket",
                "ticket_id": req.ticket_id,
                "final_action": result.get("final_action"),
                "human_review_required": result.get("human_review_required"),
            },
            ensure_ascii=False,
        ),
    )
    return _ticket_response_from_result(req, result, tid)


async def _agent_ticket_via_harness(
    req: TicketAgentRequest, settings, tid: str | None
) -> TicketAgentResponse:
    """Route /agent/ticket through the unified Harness."""
    from app.agent.harness import run_agent_harness

    uc_dict = req.user_context.model_dump() if req.user_context else {}
    result = await run_agent_harness(
        objective=req.user_query,
        tenant_id=uc_dict.get("tenant_id", "default"),
        user_id=req.customer_id or "anonymous",
        user_context=uc_dict,
        session_id=req.session_id,
        ticket_id=req.ticket_id,
    )
    return _harness_result_to_ticket_response(result, req, tid)


def _harness_result_to_ticket_response(result, req: TicketAgentRequest, tid: str | None) -> TicketAgentResponse:
    """Map AgentHarnessResult to TicketAgentResponse for frontend compatibility."""
    # Status mapping
    action_map = {
        "completed": "draft_ready",
        "waiting_approval": "await_human_review",
        "failed": "error",
        "terminated": "error",
    }
    final_action = action_map.get(result.status, result.status)

    return TicketAgentResponse(
        ticket_id=req.ticket_id,
        user_query=req.user_query,
        final_action=final_action,
        human_review_required=result.human_review_required,
        draft_reply=result.final_answer,
        ticket_note=f"Harness run_id={result.run_id}" if result.errors else None,
        retrieval_query=req.user_query,
        routed_domains=[],
        retrieved_chunks=[],
        gate_passed=True,
        gate_error_code=None,
        router_trace=None,
        policy_result=None,
        audit_trace=result.audit_trace,
        trace_id=tid,
    )


async def _run_harness_shadow(req: TicketAgentRequest, settings) -> None:
    """Shadow mode: run Harness in parallel for comparison logging."""
    try:
        from app.agent.harness import run_agent_harness
        uc_dict = req.user_context.model_dump() if req.user_context else {}
        result = await run_agent_harness(
            objective=req.user_query,
            tenant_id=uc_dict.get("tenant_id", "default"),
            user_id=req.customer_id or "anonymous",
            user_context=uc_dict,
            session_id=req.session_id,
            ticket_id=req.ticket_id,
        )
        logger.info(
            "HARNESS_SHADOW run_id=%s status=%s answer_len=%d",
            result.run_id, result.status, len(result.final_answer or ""),
        )
    except Exception as e:
        logger.warning("HARNESS_SHADOW failed: %s", e)


async def _agent_ticket_stream_events(req: TicketAgentRequest, tid: str | None) -> AsyncIterator[str]:
    """SSE 事件流（async 生成器，支持 async 图节点）。"""
    settings = get_settings()
    uc_dict = req.user_context.model_dump() if req.user_context else {}
    try:
        async for event_type, payload in iter_ticket_agent_sse(
            ticket_id=req.ticket_id,
            user_query=req.user_query,
            user_context=uc_dict,
            trace_id=tid,
            top_k=req.top_k,
            customer_id=req.customer_id,
            customer_tier=req.customer_tier,
            session_id=req.session_id,
            settings=settings,
        ):
            yield format_sse_event(event_type, payload)
    except RuntimeError as e:
        yield format_sse_event("error", {"message": str(e), "status_code": 503})
    except Exception as e:
        logger.exception("agent/ticket/stream 失败")
        yield format_sse_event("error", {"message": str(e)})
@router.post("/agent/ticket/stream")
async def agent_ticket_stream(req: TicketAgentRequest, request: Request) -> StreamingResponse:
    """SSE 流式工单 Agent：step（audit 步骤）+ token（草稿增量）+ done。"""
    tid = getattr(request.state, "trace_id", None)

    async def _gen():
            async for chunk in _agent_ticket_stream_events(req, tid):
                yield chunk
            await asyncio.sleep(0)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Agent Harness API ────────────────────────────────────────────

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    objective: str = Field(..., description="Task objective / user query")
    tenant_id: str = Field(default="default")
    user_id: str = Field(default="anonymous")
    session_id: str | None = None
    ticket_id: str | None = None
    budget: dict | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    final_answer: str | None = None
    final_action: str | None = None
    human_review_required: bool = False
    total_steps: int = 0
    total_tool_calls: int = 0
    total_latency_ms: float = 0.0
    tool_error_count: int = 0
    permission_deny_count: int = 0
    errors: list[dict] = []
    approvals: list[dict] = []


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(req: AgentRunRequest, request: Request):
    """Execute an agent run through the full harness: plan → execute → evaluate → HITL."""
    from app.agent.harness import run_agent_harness

    tenant_id = getattr(request.state, "tenant_id", None) or req.tenant_id

    result = await run_agent_harness(
        objective=req.objective,
        tenant_id=tenant_id,
        user_id=req.user_id,
        session_id=req.session_id,
        ticket_id=req.ticket_id,
        budget=req.budget,
    )

    return AgentRunResponse(
        run_id=result.run_id,
        status=result.status,
        final_answer=result.final_answer,
        final_action=result.final_action,
        human_review_required=result.human_review_required,
        total_steps=result.total_steps,
        total_tool_calls=result.total_tool_calls,
        total_latency_ms=result.total_latency_ms,
        tool_error_count=result.tool_error_count,
        permission_deny_count=result.permission_deny_count,
        errors=result.errors,
        approvals=result.approvals,
    )
