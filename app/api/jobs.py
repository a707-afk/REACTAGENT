"""Jobs API: submit and query async ingestion/eval/agent tasks."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models.ingestion_job import IngestionJob
from app.worker.queue import enqueue_job, get_job_status, list_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Request / Response models ──────────────────────────────────────

class JobSubmitRequest(BaseModel):
    task_type: str = Field(
        ...,
        description="Task type: ingest_document | run_eval | process_agent_job",
    )
    document_id: str | None = Field(default=None, description="Document ID for ingest tasks")
    task_params: dict[str, Any] | None = Field(default=None, description="Optional task parameters")


class JobResponse(BaseModel):
    id: str
    tenant_id: str
    document_id: str | None
    task_type: str
    status: str
    progress: int
    error_message: str | None
    retry_count: int
    max_retries: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    offset: int
    limit: int


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("", response_model=JobResponse, status_code=201)
async def submit_job(
    body: JobSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Submit an async job to the task queue."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = getattr(request.state, "tenant_id", "default")

    valid_types = {"ingest_document", "run_eval", "process_agent_job"}
    if body.task_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_type. Must be one of: {', '.join(sorted(valid_types))}",
        )

    job = await enqueue_job(
        session=db,
        task_type=body.task_type,
        tenant_id=tenant_id,
        document_id=body.document_id,
        task_params=body.task_params,
    )
    await db.commit()
    return _job_to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Get job status by ID."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = getattr(request.state, "tenant_id", "default")
    job = await get_job_status(db, job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("", response_model=JobListResponse)
async def list_all_jobs(
    request: Request,
    status: str | None = Query(default=None, description="Filter by status"),
    task_type: str | None = Query(default=None, description="Filter by task_type"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """List jobs with pagination and filtering."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    tenant_id = getattr(request.state, "tenant_id", "default")
    jobs, total = await list_jobs(
        db,
        tenant_id=tenant_id,
        status=status,
        task_type=task_type,
        offset=offset,
        limit=limit,
    )
    return JobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
        offset=offset,
        limit=limit,
    )


# ── Helpers ────────────────────────────────────────────────────────

def _job_to_response(job: IngestionJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        document_id=job.document_id,
        task_type=job.task_type,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        created_at=str(job.created_at),
        updated_at=str(job.updated_at),
    )
