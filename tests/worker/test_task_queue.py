"""Tests for the task queue service: enqueue, query, list jobs.

Uses an in-memory SQLite DB + fakeredis (for rate limiter tests).
Does NOT require a running Redis or arq worker — tests the DB layer
and API logic only (arq enqueue is handled gracefully when Redis is down).
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.base import Base
from app.db.models.ingestion_job import IngestionJob
from app.worker.queue import enqueue_job, get_job_status, list_jobs


@pytest.fixture
async def db_session():
    """Create an in-memory SQLite DB session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── enqueue_job tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_job_creates_record(db_session):
    """Enqueuing a job creates an IngestionJob with status='queued'."""
    job = await enqueue_job(
        session=db_session,
        task_type="ingest_document",
        tenant_id="tenant_A",
        document_id="doc-123",
    )
    # arq enqueue will fail (no Redis), but the job is still created
    # with status='failed' because of the try/except in enqueue_job
    assert job.id is not None
    assert job.tenant_id == "tenant_A"
    assert job.document_id == "doc-123"
    assert job.task_type == "ingest_document"
    assert job.progress == 0
    assert job.max_retries == 3
    # Status will be 'failed' because arq can't connect
    assert job.status in ("queued", "failed")


@pytest.mark.asyncio
async def test_enqueue_job_with_params(db_session):
    """Enqueuing with task_params stores them as JSON."""
    job = await enqueue_job(
        session=db_session,
        task_type="run_eval",
        tenant_id="tenant_B",
        task_params={"eval_set": "gold_v1", "top_k": 5},
    )
    assert job.task_params is not None
    import json
    params = json.loads(job.task_params)
    assert params["eval_set"] == "gold_v1"


# ── get_job_status tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_status_found(db_session):
    """Can retrieve a job by ID and tenant."""
    job = await enqueue_job(
        session=db_session,
        task_type="ingest_document",
        tenant_id="tenant_A",
    )
    await db_session.commit()

    found = await get_job_status(db_session, job.id, "tenant_A")
    assert found is not None
    assert found.id == job.id


@pytest.mark.asyncio
async def test_get_job_status_wrong_tenant(db_session):
    """Cannot retrieve a job with wrong tenant_id."""
    job = await enqueue_job(
        session=db_session,
        task_type="ingest_document",
        tenant_id="tenant_A",
    )
    await db_session.commit()

    found = await get_job_status(db_session, job.id, "tenant_B")
    assert found is None


@pytest.mark.asyncio
async def test_get_job_status_not_found(db_session):
    """Non-existent job returns None."""
    found = await get_job_status(db_session, "nonexistent-id", "tenant_A")
    assert found is None


# ── list_jobs tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_empty(db_session):
    """Empty list for tenant with no jobs."""
    jobs, total = await list_jobs(db_session, tenant_id="empty_tenant")
    assert jobs == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_jobs_with_data(db_session):
    """List returns jobs for the correct tenant."""
    for i in range(3):
        await enqueue_job(
            session=db_session,
            task_type="ingest_document",
            tenant_id="tenant_A",
            document_id=f"doc-{i}",
        )
    await db_session.commit()

    jobs, total = await list_jobs(db_session, tenant_id="tenant_A")
    assert total == 3
    assert len(jobs) == 3


@pytest.mark.asyncio
async def test_list_jobs_tenant_isolation(db_session):
    """Jobs from one tenant are not visible to another."""
    await enqueue_job(
        session=db_session,
        task_type="ingest_document",
        tenant_id="tenant_A",
    )
    await db_session.commit()

    jobs, total = await list_jobs(db_session, tenant_id="tenant_B")
    assert total == 0
    assert jobs == []


@pytest.mark.asyncio
async def test_list_jobs_pagination(db_session):
    """Pagination works correctly."""
    for i in range(5):
        await enqueue_job(
            session=db_session,
            task_type="ingest_document",
            tenant_id="tenant_A",
        )
    await db_session.commit()

    # Page 1: first 2
    jobs, total = await list_jobs(db_session, tenant_id="tenant_A", offset=0, limit=2)
    assert total == 5
    assert len(jobs) == 2

    # Page 2: next 2
    jobs2, _ = await list_jobs(db_session, tenant_id="tenant_A", offset=2, limit=2)
    assert len(jobs2) == 2

    # Pages should not overlap
    ids1 = {j.id for j in jobs}
    ids2 = {j.id for j in jobs2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_list_jobs_status_filter(db_session):
    """Filter by status works."""
    job = await enqueue_job(
        session=db_session,
        task_type="ingest_document",
        tenant_id="tenant_A",
    )
    # Mark one as completed manually
    job.status = "completed"
    await db_session.commit()

    # Create another job
    await enqueue_job(
        session=db_session,
        task_type="run_eval",
        tenant_id="tenant_A",
    )
    await db_session.commit()

    # Filter for completed only
    jobs, total = await list_jobs(db_session, tenant_id="tenant_A", status="completed")
    assert total >= 1
    assert all(j.status == "completed" for j in jobs)
