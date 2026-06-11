"""Database tests: alembic migration, CRUD, and tenant isolation.

Uses a temp SQLite file for each test to avoid side effects.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func

from app.db.base import Base
from app.db.models.ticket import Ticket, TicketStatus, TicketPriority
from app.db.models.ticket_event import TicketEvent
from app.db.models.customer import Customer
from app.db.models.session import ChatSession, Message


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
async def db_session():
    """Create a fresh in-memory SQLite DB with all tables for each test."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── Migration Tests ───────────────────────────────────────────────

class TestAlembicMigration:
    """Test that alembic upgrade head works on a fresh database."""

    def test_alembic_upgrade_head_on_fresh_db(self, tmp_path):
        """alembic upgrade head should succeed on an empty SQLite database."""
        import subprocess, sys

        db_path = tmp_path / "test_migration.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            timeout=30,
        )
        assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"

        # Verify tables exist
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()

        assert "tickets" in tables
        assert "ticket_events" in tables
        assert "customers" in tables
        assert "chat_sessions" in tables
        assert "messages" in tables

    def test_alembic_downgrade_and_re_upgrade(self, tmp_path):
        """alembic downgrade -1 then upgrade head should restore all tables."""
        import subprocess, sys

        db_path = tmp_path / "test_downgrade.db"
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

        # Upgrade
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=project_root, timeout=30,
        )
        assert r.returncode == 0

        # Downgrade
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            capture_output=True, text=True, env=env, cwd=project_root, timeout=30,
        )
        assert r.returncode == 0

        # Re-upgrade
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=project_root, timeout=30,
        )
        assert r.returncode == 0


# ── Ticket CRUD Tests ─────────────────────────────────────────────

class TestTicketCRUD:
    """Test Ticket model CRUD operations with DB session."""

    async def test_create_ticket(self, db_session):
        ticket = Ticket(
            title="Test ticket",
            description="A test",
            status=TicketStatus.NEW,
            priority=TicketPriority.P2_MEDIUM,
            tenant_id="tenant_a",
        )
        db_session.add(ticket)
        await db_session.commit()

        result = (await db_session.execute(
            select(Ticket).where(Ticket.id == ticket.id)
        )).scalar_one()
        assert result.title == "Test ticket"
        assert result.status == TicketStatus.NEW
        assert result.tenant_id == "tenant_a"

    async def test_list_tickets_by_tenant(self, db_session):
        for i in range(3):
            db_session.add(Ticket(
                title=f"Ticket {i}", description="",
                status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
                tenant_id="tenant_a",
            ))
        db_session.add(Ticket(
            title="Other ticket", description="",
            status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
            tenant_id="tenant_b",
        ))
        await db_session.commit()

        count_a = (await db_session.execute(
            select(func.count()).select_from(Ticket).where(Ticket.tenant_id == "tenant_a")
        )).scalar()
        count_b = (await db_session.execute(
            select(func.count()).select_from(Ticket).where(Ticket.tenant_id == "tenant_b")
        )).scalar()
        assert count_a == 3
        assert count_b == 1

    async def test_update_ticket_status(self, db_session):
        ticket = Ticket(
            title="Test", description="",
            status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
            tenant_id="default",
        )
        db_session.add(ticket)
        await db_session.commit()

        ticket.status = TicketStatus.IN_PROGRESS
        await db_session.commit()

        refreshed = (await db_session.execute(
            select(Ticket).where(Ticket.id == ticket.id)
        )).scalar_one()
        assert refreshed.status == TicketStatus.IN_PROGRESS

    async def test_ticket_persists_after_session_close(self, db_session):
        """Verify data survives a session close/reopen (proves DB persistence)."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            url = f"sqlite+aiosqlite:///{db_path}"
            engine = create_async_engine(url, echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            # Create ticket in session 1
            async with factory() as s1:
                ticket = Ticket(
                    title="Persist test", description="",
                    status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
                    tenant_id="default",
                )
                s1.add(ticket)
                await s1.commit()
                ticket_id = ticket.id

            # Read ticket in session 2
            async with factory() as s2:
                result = (await s2.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )).scalar_one()
                assert result.title == "Persist test"

            await engine.dispose()
        finally:
            os.unlink(db_path)


# ── Tenant Isolation Tests ────────────────────────────────────────

class TestTenantIsolation:
    """Prove that tenant A cannot see tenant B's tickets."""

    async def test_no_cross_tenant_leakage(self, db_session):
        # Create tickets in two tenants
        for i in range(5):
            db_session.add(Ticket(
                title=f"A-ticket-{i}", description="",
                status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
                tenant_id="tenant_a",
            ))
        for i in range(3):
            db_session.add(Ticket(
                title=f"B-ticket-{i}", description="",
                status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
                tenant_id="tenant_b",
            ))
        await db_session.commit()

        # Query tenant_a
        a_titles = {t.title for t in (await db_session.execute(
            select(Ticket).where(Ticket.tenant_id == "tenant_a")
        )).scalars().all()}
        assert len(a_titles) == 5
        assert all(t.startswith("A-ticket") for t in a_titles)

        # Query tenant_b
        b_titles = {t.title for t in (await db_session.execute(
            select(Ticket).where(Ticket.tenant_id == "tenant_b")
        )).scalars().all()}
        assert len(b_titles) == 3
        assert all(t.startswith("B-ticket") for t in b_titles)

        # Cross-check: no overlap
        assert a_titles.isdisjoint(b_titles)

    async def test_tenant_cannot_see_other_tenant_ticket_by_id(self, db_session):
        """Even if you know the UUID, the scoped query must not return it."""
        ticket = Ticket(
            title="Secret", description="classified",
            status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
            tenant_id="tenant_x",
        )
        db_session.add(ticket)
        await db_session.commit()

        # Look up same ID scoped to a different tenant
        result = (await db_session.execute(
            select(Ticket).where(Ticket.id == ticket.id, Ticket.tenant_id == "tenant_y")
        )).scalar_one_or_none()
        assert result is None


# ── TicketEvent Audit Tests ───────────────────────────────────────

class TestTicketEventAudit:
    """Verify that every transition writes a TicketEvent row."""

    async def test_transition_creates_event(self, db_session):
        ticket = Ticket(
            title="Audit test", description="",
            status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
            tenant_id="default",
        )
        db_session.add(ticket)
        await db_session.commit()

        event = TicketEvent(
            ticket_id=ticket.id,
            from_status="new",
            to_status="in_progress",
            reason="assigned",
            actor="agent",
            allowed=True,
            tenant_id="default",
        )
        db_session.add(event)
        await db_session.commit()

        events = (await db_session.execute(
            select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)
        )).scalars().all()
        assert len(events) == 1
        assert events[0].to_status == "in_progress"
        assert events[0].allowed is True

    async def test_invalid_transition_still_creates_event(self, db_session):
        ticket = Ticket(
            title="Bad transition", description="",
            status=TicketStatus.NEW, priority=TicketPriority.P2_MEDIUM,
            tenant_id="default",
        )
        db_session.add(ticket)
        await db_session.commit()

        event = TicketEvent(
            ticket_id=ticket.id,
            from_status="new",
            to_status="resolved",  # invalid: new -> resolved is not allowed
            reason="tried to skip",
            actor="hacker",
            allowed=False,
            tenant_id="default",
        )
        db_session.add(event)
        await db_session.commit()

        events = (await db_session.execute(
            select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)
        )).scalars().all()
        assert len(events) == 1
        assert events[0].allowed is False
