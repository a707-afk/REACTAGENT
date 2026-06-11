from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.policy.engine import evaluate_policy
from app.policy.models import PolicyAction, PolicyEvalResult
from app.citation_verify import citation_overlap_ratio, sentence_level_grounding
from app.config import get_settings
from app.domain_router import RouterResult
from app.vector_index import get_vector_index
from app.llm import chat_completion
from app.observability import log_structured_event
from app.retrieval_gates import evaluate_similarity_gate
from app.retrieval_pipeline import retrieve_scored_nodes
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ChunkHit,
    CitationBlock,
    RetrieveRequest,
    RetrieveResponse,
    UserContext,
)
from app.sse import chunk_text, format_sse_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rag"])


def _heading_from_meta(meta: dict[str, Any]) -> str | None:
    return meta.get("header_path") or meta.get("heading") or None


def _retrieval_query_field(user_query: str, effective: str) -> str | None:
    if (effective or "").strip() == (user_query or "").strip():
        return None
    return effective


def _router_trace_dict(rr: RouterResult | None) -> dict[str, Any] | None:
    if rr is None:
        return None
    base: dict[str, Any] = {
        "allowed_domains": list(rr.allowed_domains),
        "primary_domain": rr.primary_domain,
        "confidence": rr.confidence,
        "method": rr.method,
        "raw_confidence": rr.raw_confidence,
        "domain_weights": {d: float(w) for d, w in rr.domain_weights},
    }
    if rr.routing_trace is not None:
        base["routing_trace"] = rr.routing_trace
    return base


def _chunks_from_scored(scored) -> list[ChunkHit]:
    chunks: list[ChunkHit] = []
    for sn in scored:
        node = sn.node
        meta = dict(node.metadata or {})
        chunks.append(
            ChunkHit(
                text=node.get_content(),
                score=float(sn.score) if sn.score is not None else None,
                file_path=meta.get("file_path"),
                file_name=meta.get("file_name"),
                heading=_heading_from_meta(meta),
                node_id=node.node_id,
                domain=meta.get("domain"),
            )
        )
    return chunks


def _log_event(
    trace_id: str | None,
    event: str,
    payload: dict[str, Any],
) -> None:
    log_structured_event(trace_id, event, **payload)


def _user_context_for_policy(uc: UserContext | None) -> dict[str, Any] | None:
    if uc is None:
        return None
    return {
        "tenant_id": uc.tenant_id,
        "roles": list(uc.roles or []),
        "department": uc.department,
        "security_clearance": uc.security_clearance,
    }


def _policy_response_fields(pe: PolicyEvalResult | None) -> dict[str, Any]:
    if pe is None:
        return {
            "policy_risk_level": None,
            "policy_action": None,
            "policy_warnings": [],
            "policy_hits": [],
            "requires_human_review": None,
        }
    pa = pe.policy_action
    if isinstance(pa, PolicyAction):
        pa_s = pa.value
    else:
        pa_s = str(pa) if pa is not None else None
    return {
        "policy_risk_level": pe.policy_risk_level,
        "policy_action": pa_s,
        "policy_warnings": list(pe.policy_warnings),
        "policy_hits": list(pe.policy_hits),
        "requires_human_review": pe.requires_human_review,
    }


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest, request: Request) -> RetrieveResponse:
    tid = getattr(request.state, "trace_id", None)
    settings = get_settings()
    pe = evaluate_policy(
        req.query,
        settings,
        trace_id=tid,
        user_context_summary=_user_context_for_policy(req.user_context),
        endpoint="retrieve",
    )
    if pe.should_skip_rag:
        _log_event(
            tid,
            "retrieve",
            {
                "query": req.query[:500],
                "behavior_guard": pe.intercept_reason_code,
                **{k: v for k, v in _policy_response_fields(pe).items() if k != "policy_hits"},
            },
        )
        return RetrieveResponse(
            query=req.query,
            retrieval_query=None,
            chunks=[],
            gate_passed=False,
            error_code=pe.intercept_reason_code or "POLICY_HIT",
            behavior=pe.behavior or "human_review",
            refusal_reason_code=pe.intercept_reason_code,
            ranked_quality_scores=[],
            router_trace=None,
            trace_id=tid,
            **_policy_response_fields(pe),
        )
    try:
        index = get_vector_index()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    sr = retrieve_scored_nodes(
        index,
        req.query,
        req.top_k,
        settings,
        use_query_rewrite=req.use_query_rewrite,
        user_context=req.user_context,
        skip_domain_router=req.skip_domain_router,
        trace_id=tid,
    )
    scored = sr.nodes
    chunks = _chunks_from_scored(scored)
    rq_field = _retrieval_query_field(req.query, sr.retrieval_query)
    rt_dict = _router_trace_dict(sr.router_result)

    if not scored:
        return RetrieveResponse(
            query=req.query,
            retrieval_query=rq_field,
            chunks=chunks,
            gate_passed=False,
            error_code="NO_RESULTS",
            ranked_quality_scores=[],
            router_trace=rt_dict,
            trace_id=tid,
            **_policy_response_fields(pe),
        )

    gate = evaluate_similarity_gate(scored, settings, trace_id=tid)
    return RetrieveResponse(
        query=req.query,
        retrieval_query=rq_field,
        chunks=chunks,
        gate_passed=gate.passed,
        error_code=None if gate.passed else gate.error_code,
        ranked_quality_scores=gate.ranked_scores,
        router_trace=rt_dict,
        trace_id=tid,
        **_policy_response_fields(pe),
    )


SYS_PROMPT = (
    "你是根据「参考资料」回答问题的助手。\n"
    "规则：\n"
    "1) 只使用参考资料中出现的信息，不要编造。\n"
    "2) 若资料中没有答案，请明确说「根据当前资料无法回答」。\n"
    "3) 需要引用时在正文中使用 [1]、[2] 等形式对应条目编号。\n"
)


def _execute_chat(req: ChatRequest, tid: str | None) -> ChatResponse:
    """同步执行 /chat 核心逻辑，供 JSON 与 SSE 共用。"""
    settings = get_settings()
    pe = evaluate_policy(
        req.query,
        settings,
        trace_id=tid,
        user_context_summary=_user_context_for_policy(req.user_context),
        endpoint="chat",
    )
    if pe.should_skip_rag:
        _log_event(
            tid,
            "chat",
            {
                "query": req.query[:500],
                "refused": "BEHAVIOR_GUARD",
                "code": pe.intercept_reason_code,
            },
        )
        return ChatResponse(
            query=req.query,
            retrieval_query=None,
            answer=pe.message_zh or "",
            citations=[],
            chunks_used=0,
            refused=True,
            error_code=pe.intercept_reason_code or "POLICY_HIT",
            behavior=pe.behavior or "human_review",
            refusal_reason_code=pe.intercept_reason_code,
            ranked_quality_scores=[],
            router_trace=None,
            trace_id=tid,
            citation_overlap_ratio=None,
            **_policy_response_fields(pe),
        )
    try:
        index = get_vector_index()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    sr = retrieve_scored_nodes(
        index,
        req.query,
        req.top_k,
        settings,
        use_query_rewrite=req.use_query_rewrite,
        user_context=req.user_context,
        skip_domain_router=req.skip_domain_router,
        trace_id=tid,
    )
    scored = sr.nodes
    rq_field = _retrieval_query_field(req.query, sr.retrieval_query)
    rt_dict = _router_trace_dict(sr.router_result)

    if not scored:
        _log_event(tid, "chat", {"query": req.query[:500], "refused": "NO_RESULTS"})
        return ChatResponse(
            query=req.query,
            retrieval_query=rq_field,
            answer=settings.refusal_no_results,
            citations=[],
            chunks_used=0,
            refused=True,
            error_code="NO_RESULTS",
            ranked_quality_scores=[],
            router_trace=rt_dict,
            trace_id=tid,
            citation_overlap_ratio=None,
            **_policy_response_fields(pe),
        )

    gate = evaluate_similarity_gate(scored, settings, trace_id=tid)
    if not gate.passed:
        _log_event(
            tid,
            "chat",
            {"query": req.query[:500], "refused": gate.error_code},
        )
        return ChatResponse(
            query=req.query,
            retrieval_query=rq_field,
            answer=settings.refusal_gate_fail,
            citations=[],
            chunks_used=0,
            refused=True,
            error_code=gate.error_code or "GATE_FAIL",
            ranked_quality_scores=gate.ranked_scores,
            router_trace=rt_dict,
            trace_id=tid,
            citation_overlap_ratio=None,
            **_policy_response_fields(pe),
        )

    parts: list[str] = []
    cites: list[CitationBlock] = []
    chunk_plain: list[str] = []
    chunks_with_meta: list[dict] = []
    for i, sn in enumerate(scored):
        node = sn.node
        meta = dict(node.metadata or {})
        text = node.get_content()
        chunk_plain.append(text)
        chunks_with_meta.append(
            {
                "text": text,
                "node_id": node.node_id,
                "file_name": meta.get("file_name"),
                "file_path": meta.get("file_path"),
            }
        )
        fn = meta.get("file_name") or ""
        fp = meta.get("file_path") or ""
        hd = _heading_from_meta(meta)
        parts.append(
            f"[{i + 1}] 文件: {fn} ({fp})\n标题路径: {hd or '无'}\n{text}\n"
        )
        cites.append(
            CitationBlock(
                index=i + 1,
                file_path=fp or None,
                file_name=fn or None,
                heading=hd,
                excerpt=text[:400] + ("…" if len(text) > 400 else ""),
            )
        )

    user_block = (
        "参考资料：\n\n"
        + "\n---\n".join(parts)
        + "\n\n用户问题：\n"
        + req.query.strip()
    )
    try:
        answer = chat_completion(SYS_PROMPT, user_block)
    except RuntimeError as e:
        logger.exception("LLM 调用失败")
        raise HTTPException(status_code=500, detail=str(e)) from e

    ov = citation_overlap_ratio(answer, chunk_plain)
    grounding_report = sentence_level_grounding(answer, chunks_with_meta)
    grounding_dict = grounding_report.to_dict()
    _log_event(
        tid,
        "chat",
        {
            "query": req.query[:500],
            "chunks_used": len(scored),
            "citation_overlap_ratio": ov,
            "grounding_passed": grounding_dict.get("passed"),
            "unsupported_sentence_rate": grounding_dict.get("unsupported_sentence_rate"),
            "router": rt_dict,
        },
    )
    return ChatResponse(
        query=req.query,
        retrieval_query=rq_field,
        answer=answer,
        citations=cites,
        chunks_used=len(scored),
        refused=False,
        error_code=None,
        ranked_quality_scores=gate.ranked_scores,
        router_trace=rt_dict,
        trace_id=tid,
        citation_overlap_ratio=ov,
        grounding=grounding_dict,
        **_policy_response_fields(pe),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    tid = getattr(request.state, "trace_id", None)
    return _execute_chat(req, tid)


def _chat_stream_events(req: ChatRequest, tid: str | None) -> Iterator[str]:
    try:
        resp = _execute_chat(req, tid)
    except HTTPException as e:
        yield format_sse_event("error", {"message": str(e.detail), "status_code": e.status_code})
        return
    except Exception as e:
        logger.exception("chat/stream 失败")
        yield format_sse_event("error", {"message": str(e)})
        return

    answer = resp.answer or ""
    if answer and not resp.refused:
        for piece in chunk_text(answer):
            yield format_sse_event("token", {"text": piece})

    yield format_sse_event("done", resp.model_dump(mode="json"))


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    """SSE 流式问答：token 增量 + done（完整 ChatResponse 摘要）。"""
    tid = getattr(request.state, "trace_id", None)

    async def _gen():
        for chunk in _chat_stream_events(req, tid):
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
