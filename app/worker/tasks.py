"""Task definitions for the arq worker.

Each function signature: ``async def task_name(ctx, **params) -> dict``.
The ``ctx`` dict contains ``redis`` and other arq-provided context.

Tasks are responsible for:
1. Updating IngestionJob status in DB.
2. Doing the actual work.
3. Recording success/failure.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Task: ingest_document ─────────────────────────────────────────

async def ingest_document(ctx: dict[str, Any], *, job_id: str, tenant_id: str, document_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ingest a document: parse → chunk → embed → write to Qdrant + BM25.

    This task reads the uploaded file from storage and runs the full
    ingestion pipeline defined in app.ingestion.pipeline.
    """
    from app.db.engine import get_db_session
    from app.db.models.ingestion_job import IngestionJob
    from app.db.models.document import Document

    logger.info("ingest_document started: job_id=%s document_id=%s", job_id, document_id)

    async with get_db_session() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            logger.error("IngestionJob %s not found", job_id)
            return {"status": "failed", "error": "job not found"}

        # Update status to running
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # Get document info
        doc = await session.get(Document, document_id)
        if doc is None:
            await _mark_job_failed(job_id, f"Document {document_id} not found")
            return {"status": "failed", "job_id": job_id, "error": "document not found"}

        storage_path = doc.storage_path
        file_name = doc.file_name
        mime_type = doc.mime_type
        tenant_id = doc.tenant_id

    try:
        from pathlib import Path
        from app.ingestion.pipeline import run_ingestion_pipeline

        # Read file from storage
        path = Path(storage_path)
        if not path.exists():
            await _mark_job_failed(job_id, f"File not found: {storage_path}")
            return {"status": "failed", "job_id": job_id, "error": "file not found"}

        file_data = path.read_bytes()

        # Parse params
        domain = None
        security_level = "internal"
        allowed_roles = None
        if params:
            domain = params.get("domain")
            security_level = params.get("security_level", "internal")
            allowed_roles = params.get("allowed_roles")

        # Run the full ingestion pipeline
        result = await run_ingestion_pipeline(
            file_data=file_data,
            file_name=file_name,
            tenant_id=tenant_id,
            job_id=job_id,
            mime_type=mime_type,
            domain=domain,
            security_level=security_level,
            allowed_roles=allowed_roles,
        )

        logger.info(
            "ingest_document completed: job_id=%s chunks=%d pages=%d",
            job_id, result.chunks_created, result.pages_parsed,
        )
        return {
            "status": "completed",
            "job_id": job_id,
            "document_id": result.document_id,
            "chunks_created": result.chunks_created,
            "pages_parsed": result.pages_parsed,
        }

    except Exception as e:
        logger.exception("ingest_document failed: job_id=%s error=%s", job_id, e)
        await _mark_job_failed(job_id, str(e))
        return {"status": "failed", "job_id": job_id, "error": str(e)}


# ── Task: run_eval ─────────────────────────────────────────────────

async def run_eval(ctx: dict[str, Any], *, job_id: str, tenant_id: str, eval_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a RAG evaluation suite using the eval runner.

    eval_config may contain:
    - category: specific category to evaluate (default: all)
    - dry_run: whether to run in dry-run mode (default: False)
    - output_prefix: prefix for report filenames
    """
    from app.db.engine import get_db_session
    from app.db.models.ingestion_job import IngestionJob

    logger.info("run_eval started: job_id=%s config=%s", job_id, eval_config)

    async with get_db_session() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return {"status": "failed", "error": "job not found"}
        job.status = "running"
        job.progress = 5
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        import sys
        from pathlib import Path

        # Add scripts dir to path
        scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from run_eval_rag import load_cases, run_eval as run_rag_eval

        category = (eval_config or {}).get("category")
        dry_run = (eval_config or {}).get("dry_run", True)

        # Update progress
        async with get_db_session() as session:
            job = await session.get(IngestionJob, job_id)
            if job:
                job.progress = 15
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()

        # Load cases
        cases = load_cases(category)
        logger.info("run_eval: loaded %d cases for category=%s", len(cases), category or "all")

        # Update progress
        async with get_db_session() as session:
            job = await session.get(IngestionJob, job_id)
            if job:
                job.progress = 30
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()

        # Run evaluation
        summary = run_rag_eval(cases, dry_run=dry_run)
        metrics = summary["metrics"]

        logger.info(
            "run_eval done: cases=%d recall@5=%.4f mrr@10=%.4f",
            summary["total_cases"], metrics["recall_at_5"], metrics["mrr_at_10"],
        )

        # Mark completed
        async with get_db_session() as session:
            job = await session.get(IngestionJob, job_id)
            if job:
                job.status = "completed"
                job.progress = 100
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()

        return {
            "status": "completed",
            "job_id": job_id,
            "summary": {
                "total_cases": summary["total_cases"],
                "recall_at_5": metrics["recall_at_5"],
                "mrr_at_10": metrics["mrr_at_10"],
                "ndcg_at_10": metrics["ndcg_at_10"],
            },
        }

    except Exception as e:
        logger.exception("run_eval failed: job_id=%s error=%s", job_id, e)
        await _mark_job_failed(job_id, str(e))
        return {"status": "failed", "job_id": job_id, "error": str(e)}


# ── Task: process_agent_job ────────────────────────────────────────

async def process_agent_job(ctx: dict[str, Any], *, job_id: str, tenant_id: str, ticket_id: str, user_query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an async agent job (long-running ticket processing)."""
    from app.db.engine import get_db_session
    from app.db.models.ingestion_job import IngestionJob

    logger.info("process_agent_job started: job_id=%s ticket_id=%s", job_id, ticket_id)

    async with get_db_session() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return {"status": "failed", "error": "job not found"}
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        # Run the ticket through unified Agent Harness
        from app.agent.harness import run_agent_harness
        harness_result = await run_agent_harness(
            objective=user_query,
            tenant_id=tenant_id,
            user_id=params.get("customer_id", "anonymous") if params else "anonymous",
            ticket_id=ticket_id,
        )
        result = {
            "status": harness_result.status,
            "final_action": harness_result.final_action,
            "draft_reply": harness_result.final_answer,
            "human_review_required": harness_result.human_review_required,
            "trace_id": harness_result.run_id,
        }

        await _simulate_progress(ctx, job_id, steps=4)

        async with get_db_session() as session:
            job = await session.get(IngestionJob, job_id)
            if job:
                job.status = "completed"
                job.progress = 100
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()

        return {"status": "completed", "job_id": job_id, "result": result}

    except Exception as e:
        logger.exception("process_agent_job failed: job_id=%s error=%s", job_id, e)
        await _mark_job_failed(job_id, str(e))
        return {"status": "failed", "job_id": job_id, "error": str(e)}


# ── Helper functions ───────────────────────────────────────────────

async def _simulate_progress(ctx: dict[str, Any], job_id: str, steps: int = 5) -> None:
    """Simulate progress by updating the job's progress field."""
    import asyncio
    from app.db.engine import get_db_session
    from app.db.models.ingestion_job import IngestionJob

    for i in range(1, steps + 1):
        progress = int(100 * i / steps)
        async with get_db_session() as session:
            job = await session.get(IngestionJob, job_id)
            if job and job.status == "running":
                job.progress = progress
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()
        await asyncio.sleep(0.05)  # Small delay for testability


async def _mark_job_failed(job_id: str, error_message: str) -> None:
    """Mark a job as failed in the DB."""
    from app.db.engine import get_db_session
    from app.db.models.ingestion_job import IngestionJob

    async with get_db_session() as session:
        job = await session.get(IngestionJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = error_message
            job.retry_count = (job.retry_count or 0) + 1
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
