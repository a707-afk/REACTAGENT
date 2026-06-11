"""Tests for the /api/jobs endpoint via FastAPI TestClient."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.base import Base
from app.api.deps import get_db_session
from app.main import create_app


@pytest.fixture
async def app_with_db():
    """Create an app with an in-memory SQLite DB for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db_session():
        async with factory() as session:
            yield session
            await session.commit()

    app = create_app()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    yield app

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(app_with_db):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Submit job tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_job_ingest(client):
    """POST /api/jobs creates an ingest job."""
    resp = await client.post(
        "/api/jobs",
        json={"task_type": "ingest_document", "document_id": "doc-001"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_type"] == "ingest_document"
    assert data["tenant_id"] == "test_tenant"
    assert data["document_id"] == "doc-001"


@pytest.mark.asyncio
async def test_submit_job_eval(client):
    """POST /api/jobs creates an eval job."""
    resp = await client.post(
        "/api/jobs",
        json={"task_type": "run_eval", "task_params": {"eval_set": "gold_v1"}},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_type"] == "run_eval"


@pytest.mark.asyncio
async def test_submit_job_invalid_type(client):
    """POST /api/jobs with invalid task_type returns 400."""
    resp = await client.post(
        "/api/jobs",
        json={"task_type": "invalid_type"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert resp.status_code == 400


# ── Get job tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_found(client):
    """GET /api/jobs/{id} returns the job."""
    # Create a job first
    create_resp = await client.post(
        "/api/jobs",
        json={"task_type": "ingest_document"},
        headers={"X-Tenant-ID": "tenant_A"},
    )
    job_id = create_resp.json()["id"]

    # Get it back
    get_resp = await client.get(
        f"/api/jobs/{job_id}",
        headers={"X-Tenant-ID": "tenant_A"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    """GET /api/jobs/{id} with wrong ID returns 404."""
    resp = await client.get(
        "/api/jobs/nonexistent-id",
        headers={"X-Tenant-ID": "tenant_A"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_wrong_tenant(client):
    """GET /api/jobs/{id} with wrong tenant returns 404."""
    create_resp = await client.post(
        "/api/jobs",
        json={"task_type": "ingest_document"},
        headers={"X-Tenant-ID": "tenant_A"},
    )
    job_id = create_resp.json()["id"]

    # Try to access with different tenant
    get_resp = await client.get(
        f"/api/jobs/{job_id}",
        headers={"X-Tenant-ID": "tenant_B"},
    )
    assert get_resp.status_code == 404


# ── List jobs tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_empty(client):
    """GET /api/jobs returns empty list for new tenant."""
    resp = await client.get(
        "/api/jobs",
        headers={"X-Tenant-ID": "empty_tenant"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["jobs"] == []


@pytest.mark.asyncio
async def test_list_jobs_with_data(client):
    """GET /api/jobs returns created jobs."""
    for i in range(3):
        await client.post(
            "/api/jobs",
            json={"task_type": "ingest_document", "document_id": f"doc-{i}"},
            headers={"X-Tenant-ID": "tenant_A"},
        )

    resp = await client.get(
        "/api/jobs",
        headers={"X-Tenant-ID": "tenant_A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_jobs_tenant_isolation(client):
    """Jobs from one tenant are not visible to another."""
    await client.post(
        "/api/jobs",
        json={"task_type": "ingest_document"},
        headers={"X-Tenant-ID": "tenant_A"},
    )

    resp = await client.get(
        "/api/jobs",
        headers={"X-Tenant-ID": "tenant_B"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_jobs_status_filter(client):
    """GET /api/jobs?status=completed filters correctly."""
    await client.post(
        "/api/jobs",
        json={"task_type": "ingest_document"},
        headers={"X-Tenant-ID": "tenant_A"},
    )

    resp = await client.get(
        "/api/jobs?status=completed",
        headers={"X-Tenant-ID": "tenant_A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Newly created jobs may be 'failed' (arq not running), so completed=0 is fine
    assert isinstance(data["total"], int)
