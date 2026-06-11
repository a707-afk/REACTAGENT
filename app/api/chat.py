"""Chat API — RAG-augmented conversation endpoint with session memory."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_db_session, verify_api_key
from app.config import get_settings
from app.llm import chat_completion
from app.observability import log_structured_event
from app.retrieval_gates import evaluate_similarity_gate
from app.retrieval_pipeline import retrieve_scored_nodes
from app.schemas import ChatRequest, ChatResponse, CitationBlock
from app.services.session_mgr import SessionMemory
from app.sse import chunk_text, format_sse_event
from app.vector_index import get_vector_index

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

CHAT_SYSTEM_PROMPT = (
    "你是专业的客服 AI 助手。根据知识库内容回答客户问题。\n"
    "规则：\n"
    "1) 仅使用参考资料中的信息，不要编造\n"
    "2) 如果资料中无答案，明确告知并建议转人工\n"
    "3) 需要引用时使用 [1] [2] 标注\n"
    "4) 语气专业、简洁，使用中文\n"
)


def _execute_chat(req: ChatRequest, tid: str | None) -> ChatResponse:
    settings = get_settings()
    t0 = time.perf_counter()

    index = get_vector_index()
    if index is None:
        raise HTTPException(status_code=503, detail="Vector index not loaded")

    # Retrieve
    sr = retrieve_scored_nodes(
        index, req.query, req.top_k, settings,
        use_query_rewrite=req.use_query_rewrite,
        user_context=req.user_context,
        trace_id=tid,
    )

    if not sr.nodes:
        return ChatResponse(
            query=req.query,
            answer=settings.refusal_no_results,
            citations=[], chunks_used=0,
            refused=True, error_code="NO_RESULTS",
            trace_id=tid,
        )

    # Gate
    gate = evaluate_similarity_gate(sr.nodes, settings, trace_id=tid)
    if not gate.passed:
        return ChatResponse(
            query=req.query,
            answer=settings.refusal_gate_fail,
            citations=[], chunks_used=0,
            refused=True, error_code=gate.error_code or "GATE_FAIL",
            trace_id=tid,
        )

    # Build citations and prompt
    parts: list[str] = []
    cites: list[CitationBlock] = []
    chunk_texts: list[str] = []
    for i, sn in enumerate(sr.nodes):
        text = sn.node.get_content()
        meta = dict(sn.node.metadata or {})
        chunk_texts.append(text)
        fn = meta.get("file_name", "")
        parts.append(f"[{i + 1}] {fn}\n{text}\n")
        cites.append(CitationBlock(
            index=i + 1,
            file_path=meta.get("file_path"),
            file_name=fn,
            heading=meta.get("header_path") or meta.get("heading"),
            excerpt=text[:400] + ("…" if len(text) > 400 else ""),
        ))

    user_block = "参考资料：\n\n" + "\n---\n".join(parts) + "\n\n用户问题：\n" + req.query.strip()

    # LLM
    try:
        answer = chat_completion(CHAT_SYSTEM_PROMPT, user_block)
    except RuntimeError as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Citation overlap
    from app.citation_verify import citation_overlap_ratio
    ov = citation_overlap_ratio(answer, chunk_texts)

    latency = time.perf_counter() - t0
    log_structured_event(tid, "chat", query=req.query[:200], chunks=len(sr.nodes),
                         overlap=ov, latency_s=round(latency, 3))

    return ChatResponse(
        query=req.query,
        answer=answer,
        citations=cites,
        chunks_used=len(sr.nodes),
        refused=False,
        citation_overlap_ratio=ov,
        trace_id=tid,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, _auth: bool = Depends(verify_api_key)):
    tid = getattr(request.state, "trace_id", None)
    return _execute_chat(req, tid)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request, _auth: bool = Depends(verify_api_key)):
    tid = getattr(request.state, "trace_id", None)

    async def _gen():
        try:
            resp = _execute_chat(req, tid)
        except HTTPException as e:
            yield format_sse_event("error", {"message": str(e.detail), "status_code": e.status_code})
            return
        except Exception as e:
            yield format_sse_event("error", {"message": str(e)})
            return

        answer = resp.answer or ""
        if answer and not resp.refused:
            for piece in chunk_text(answer):
                yield format_sse_event("token", {"text": piece})
        yield format_sse_event("done", resp.model_dump(mode="json"))

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
