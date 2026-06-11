"""API-level tests for the tickets endpoint using httpx AsyncClient.

Uses an in-memory SQLite DB injected via dependency override.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db_session
from app.db.base import Base
from app.db.models.ticket import Ticket, TicketStatus, TicketPriority
from app.db.models.ticket_event import TicketEvent
from app.main import create_app


# ── Fixtures ──────────────────────────────────────────────────────

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
    """Async test client."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Create Ticket Tests ──────────────────────────────────────────

class TestCreateTicket:
    async def test_create_ticket_returns_200(self, client):
        resp = await client.post("/api/tickets", json={
            "title": "My ticket",
            "description": "Something broke",
            "priority": "p1_high",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My ticket"
        assert data["status"] == "new"
        assert data["priority"] == "p1_high"
        assert "id" in data
        assert "created_at" in data

    async def test_create_ticket_default_priority(self, client):
        resp = await client.post("/api/tickets", json={"title": "Default prio"})
        assert resp.status_code == 200
        assert resp.json()["priority"] == "p2_medium"

    async def test_create_ticket_invalid_priority_returns_400(self, client):
        resp = await client.post("/api/tickets", json={
            "title": "Bad",
            "priority": "invalid",
        })
        assert resp.status_code == 400


# ── List Tickets Tests ───────────────────────────────────────────

class TestListTickets:
    async def test_list_empty(self, client):
        resp = await client.get("/api/tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["tickets"] == []

    async def test_list_with_pagination(self, client):
        for i in range(5):
            await client.post("/api/tickets", json={"title": f"T{i}"})

        # Page 1
        resp = await client.get("/api/tickets?offset=0&limit=2")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["tickets"]) == 2

        # Page 2
        resp = await client.get("/api/tickets?offset=2&limit=2")
        data = resp.json()
        assert len(data["tickets"]) == 2

    async def test_list_filtered_by_status(self, client):
        r = await client.post("/api/tickets", json={"title": "T1"})
        ticket_id = r.json()["id"]

        # Transition to in_progress
        await client.patch(f"/api/tickets/{ticket_id}/transition", json={
            "status": "in_progress",
        })

        resp = await client.get("/api/tickets?status_filter=in_progress")
        data = resp.json()
        assert data["total"] == 1

        resp = await client.get("/api/tickets?status_filter=new")
        data = resp.json()
        assert data["total"] == 0


# ── Get Ticket Tests ─────────────────────────────────────────────

class TestGetTicket:
    async def test_get_existing_ticket(self, client):
        r = await client.post("/api/tickets", json={"title": "Find me"})
        ticket_id = r.json()["id"]

        resp = await client.get(f"/api/tickets/{ticket_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Find me"

    async def test_get_nonexistent_ticket_returns_404(self, client):
        resp = await client.get("/api/tickets/nonexistent-id")
        assert resp.status_code == 404


# ── Transition Tests ─────────────────────────────────────────────

class TestTransitionTicket:
    async def test_valid_transition(self, client):
        r = await client.post("/api/tickets", json={"title": "Trans"})
        ticket_id = r.json()["id"]

        resp = await client.patch(f"/api/tickets/{ticket_id}/transition", json={
            "status": "in_progress",
            "reason": "agent picked up",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    async def test_invalid_transition_returns_409(self, client):
        r = await client.post("/api/tickets", json={"title": "Bad trans"})
        ticket_id = r.json()["id"]

        # new -> resolved is not allowed
        resp = await client.patch(f"/api/tickets/{ticket_id}/transition", json={
            "status": "resolved",
        })
        assert resp.status_code == 409

    async def test_transition_sets_resolved_at(self, client):
        r = await client.post("/api/tickets", json={
            "title": "Resolve", "priority": "p0_critical",
        })
        ticket_id = r.json()["id"]

        # new -> in_progress -> resolved
        await client.patch(f"/api/tickets/{ticket_id}/transition", json={"status": "in_progress"})
        resp = await client.patch(f"/api/tickets/{ticket_id}/transition", json={"status": "resolved"})
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is not None


# ── Tenant Isolation (API-level) ─────────────────────────────────

class TestTenantIsolationAPI:
    async def test_tenant_cannot_see_other_tenant_tickets(self, client):
        # Create as tenant_a
        r = await client.post("/api/tickets", json={
            "title": "A-ticket",
        }, headers={"X-Tenant-ID": "tenant_a"})
        assert r.status_code == 200

        # List as tenant_b — should see 0
        resp = await client.get("/api/tickets", headers={"X-Tenant-ID": "tenant_b"})
        data = resp.json()
        assert data["total"] == 0

        # List as tenant_a — should see 1
        resp = await client.get("/api/tickets", headers={"X-Tenant-ID": "tenant_a"})
        data = resp.json()
        assert data["total"] == 1

    async def test_tenant_cannot_get_other_tenant_ticket_by_id(self, client):
        r = await client.post("/api/tickets", json={
            "title": "Secret",
        }, headers={"X-Tenant-ID": "tenant_x"})
        ticket_id = r.json()["id"]

        # Try to fetch as tenant_y
        resp = await client.get(f"/api/tickets/{ticket_id}", headers={"X-Tenant-ID": "tenant_y"})
        assert resp.status_code == 404

        # Fetch as correct tenant
        resp = await client.get(f"/api/tickets/{ticket_id}", headers={"X-Tenant-ID": "tenant_x"})
        assert resp.status_code == 200
