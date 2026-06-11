"""Task queue service: submit and query async jobs via arq + Redis.

This module provides the API-facing functions:
- ``enqueue_job``: Create an IngestionJob in DB + push to arq queue
- ``get_job_status``: Read job status from DB
- ``list_jobs``: Paginated list with tenant/status filters
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion_job import IngestionJob

logger = logging.getLogger(__name__)


async def enqueue_job(
    *,
    session: AsyncSession,
    task_type: str,
    tenant_id: str,
    document_id: str | None = None,
    task_params: dict[str, Any] | None = None,
    max_retries: int = 3,
    redis=None,
) -> IngestionJob:
    """Create an IngestionJob record and push it to the arq queue.

    Args:
        session: DB session
        task_type: One of ``ingest_document``, ``run_eval``, ``process_agent_job``
        tenant_id: Tenant scope
        document_id: Optional document reference
        task_params: Optional JSON-serializable params for the task
        max_retries: Maximum retry count on failure
        redis: Optional aioredis instance (for testing with fakeredis)

    Returns:
        The created IngestionJob with ``status="queued"``
    """
    job_id = str(uuid.uuid4())
    job = IngestionJob(
        id=job_id,
        tenant_id=tenant_id,
        document_id=document_id,
        status="queued",
        progress=0,
        task_type=task_type,
        task_params=json.dumps(task_params, ensure_ascii=False) if task_params else None,
        retry_count=0,
        max_retries=max_retries,
    )
    session.add(job)
    await session.flush()

    # Push to arq queue
    try:
        if redis is None:
            from app.redis_client import get_redis_pool
            redis = await get_redis_pool()
        from arq import create_pool_from_settings
        from arq.connections import RedisSettings
        from urllib.parse import urlparse

        settings = _get_settings()
        parsed = urlparse(settings.redis_url)
        redis_settings = RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            database=int(parsed.path.lstrip("/") or "0"),
            password=settings.redis_password or parsed.password or None,
        )
        arq_pool = await create_pool_from_settings(redis_settings)

        job_kwargs = {
            "job_id": job_id,
            "tenant_id": tenant_id,
        }
        if document_id:
            job_kwargs["document_id"] = document_id
        if task_params:
            job_kwargs["params"] = task_params

        await arq_pool.enqueue_job(task_type, **job_kwargs)
        logger.info("Job %s enqueued: task_type=%s", job_id, task_type)
    except Exception as e:
        # If arq enqueue fails, mark job as failed immediately
        logger.warning("Failed to enqueue job %s: %s (marking as failed)", job_id, e)
        job.status = "failed"
        job.error_message = f"Queue error: {e}"
        job.updated_at = datetime.now(timezone.utc)
        await session.flush()

    await session.refresh(job)
    return job


async def get_job_status(session: AsyncSession, job_id: str, tenant_id: str) -> IngestionJob | None:
    """Get a job by ID, scoped to tenant."""
    result = await session.execute(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    task_type: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[IngestionJob], int]:
    """List jobs with pagination and filtering.

    Returns:
        (jobs, total_count)
    """
    base_filter = IngestionJob.tenant_id == tenant_id
    if status:
        base_filter = base_filter & (IngestionJob.status == status)
    if task_type:
        base_filter = base_filter & (IngestionJob.task_type == task_type)

    # Count
    count_q = select(func.count()).select_from(IngestionJob).where(base_filter)
    total = (await session.execute(count_q)).scalar() or 0

    # Query
    q = (
        select(IngestionJob)
        .where(base_filter)
        .order_by(IngestionJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(q)
    jobs = list(result.scalars().all())
    return jobs, total


def _get_settings():
    from app.config import get_settings
    return get_settings()
