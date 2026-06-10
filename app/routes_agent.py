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
