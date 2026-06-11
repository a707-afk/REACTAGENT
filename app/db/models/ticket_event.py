"""TicketEvent model — audit trail for every ticket state transition."""
from __future__ import annotations

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, Base
from app.db.models.ticket import TicketStatus


class TicketEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ticket_events"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
    to_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="system")
    allowed: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Multi-tenant (denormalised for fast filtering)
    tenant_id: Mapped[str] = mapped_column(
        String(100), default="default", index=True, nullable=False
    )

    # Relationship
    ticket = relationship("Ticket", back_populates="events", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TicketEvent {self.id[:8]} {self.from_status}->{self.to_status}>"
