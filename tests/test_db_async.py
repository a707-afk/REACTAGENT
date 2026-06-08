"""Integration tests for DB models, state machine, and session memory."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.customer import Customer, CustomerTier
from app.db.models.ticket import Ticket, TicketPriority, TicketStatus, can_transition
from app.db.models.session import ChatSession, Message, MessageRole, SessionStatus
from app.services.ticket_sm import TicketStateMachine
from app.services.session_mgr import SessionMemory


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite for sync tests."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


class TestTicketModel:
    def test_create_and_read(self, db_session: Session):
        ticket = Ticket(
            title="Test ticket",
            description="A test",
            priority=TicketPriority.P2_MEDIUM,
            status=TicketStatus.NEW,
            tenant_id="test_tenant",
        )
        db_session.add(ticket)
        db_session.flush()
        assert ticket.id is not None
        assert ticket.tenant_id == "test_tenant"

    def test_tenant_isolation(self, db_session: Session):
        t1 = Ticket(title="T1", priority=TicketPriority.P2_MEDIUM, tenant_id="tenant_a")
        t2 = Ticket(title="T2", priority=TicketPriority.P2_MEDIUM, tenant_id="tenant_b")
        db_session.add_all([t1, t2])
        db_session.flush()

        from sqlalchemy import select
        result = db_session.execute(
            select(Ticket).where(Ticket.tenant_id == "tenant_a")
        )
        tickets = result.scalars().all()
        assert len(tickets) == 1
        assert tickets[0].title == "T1"


class TestCustomerModel:
    def test_create_customer(self, db_session: Session):
        c = Customer(name="Alice", email="alice@test.com", tier=CustomerTier.PREMIUM, tenant_id="t1")
        db_session.add(c)
        db_session.flush()
        assert c.id is not None
        assert c.tier == CustomerTier.PREMIUM


class TestSessionModel:
    def test_session_with_messages(self, db_session: Session):
        sess = ChatSession(tenant_id="t1")
        db_session.add(sess)
        db_session.flush()

        msg = Message(session_id=sess.id, role=MessageRole.USER, content="Hello")
        db_session.add(msg)
        db_session.flush()

        assert msg.id is not None
        assert msg.session_id == sess.id


class TestStateMachine:
    def test_valid_transitions(self):
        sm = TicketStateMachine("t1", TicketStatus.NEW, TicketPriority.P2_MEDIUM)
        assert sm.transition(TicketStatus.IN_PROGRESS, reason="pick up")
        assert sm.current_status == TicketStatus.IN_PROGRESS
        assert sm.transition(TicketStatus.RESOLVED, reason="fixed")
        assert sm.current_status == TicketStatus.RESOLVED

    def test_invalid_transition(self):
        sm = TicketStateMachine("t2", TicketStatus.NEW, TicketPriority.P2_MEDIUM)
        assert not sm.transition(TicketStatus.ESCALATED, reason="can't skip")
        assert sm.current_status == TicketStatus.NEW

    def test_sla_computation(self):
        sm = TicketStateMachine("t3", TicketStatus.NEW, TicketPriority.P0_CRITICAL, CustomerTier.ENTERPRISE)
        deadline = sm.compute_sla_deadline()
        assert deadline is not None

    def test_transition_function(self):
        assert can_transition(TicketStatus.NEW, TicketStatus.IN_PROGRESS)
        assert not can_transition(TicketStatus.NEW, TicketStatus.ESCALATED)
        assert can_transition(TicketStatus.CLOSED, TicketStatus.IN_PROGRESS)


class TestSessionMemory:
    def test_build_context(self):
        sm = SessionMemory("s1")
        sm.add_message("user", "I need help")
        sm.add_message("assistant", "What is your issue?")
        sm.add_message("user", "My order is missing")
        ctx = sm.build_context_prompt()
        assert "I need help" in ctx
        assert "My order is missing" in ctx

    def test_empty_context(self):
        sm = SessionMemory("s2")
        assert sm.build_context_prompt() == ""
        assert sm.turn_count() == 0

    def test_summarize(self):
        sm = SessionMemory("s3")
        sm.add_message("user", "Reset password")
        sm.add_message("assistant", "Here are the steps...")
        summary = sm.summarize_last_n(1)
        assert "Reset password" in summary
