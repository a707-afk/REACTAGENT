"""Ticket model with state machine transitions."""
from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, Base


class TicketStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    P0_CRITICAL = "p0_critical"
    P1_HIGH = "p1_high"
    P2_MEDIUM = "p2_medium"
    P3_LOW = "p3_low"


# Valid state transitions
VALID_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset({
        TicketStatus.IN_PROGRESS,
        TicketStatus.CLOSED,
    }),
    TicketStatus.IN_PROGRESS: frozenset({
        TicketStatus.WAITING_CUSTOMER,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    }),
    TicketStatus.WAITING_CUSTOMER: frozenset({
        TicketStatus.IN_PROGRESS,
        TicketStatus.CLOSED,
    }),
    TicketStatus.ESCALATED: frozenset({
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    }),
    TicketStatus.RESOLVED: frozenset({
        TicketStatus.CLOSED,
        TicketStatus.IN_PROGRESS,  # reopen
    }),
    TicketStatus.CLOSED: frozenset({
        TicketStatus.IN_PROGRESS,  # reopen
    }),
}


def can_transition(current: TicketStatus, target: TicketStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, frozenset())


class Ticket(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status_enum"),
        default=TicketStatus.NEW,
        nullable=False,
        index=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority_enum"),
        default=TicketPriority.P2_MEDIUM,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str | None] = mapped_column(String(100), index=True)
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    assignee: Mapped[str | None] = mapped_column(String(200))
    sla_deadline: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    tags_json: Mapped[str | None] = mapped_column(Text)  # JSON list

    # Multi-tenant
    tenant_id: Mapped[str] = mapped_column(String(100), default="default", index=True, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="tickets", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Ticket {self.id[:8]} [{self.status.value}] {self.title[:40]}>"
