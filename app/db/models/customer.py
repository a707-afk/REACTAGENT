"""Customer model."""
from __future__ import annotations

import enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, Base


class CustomerTier(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


# SLA minutes per tier
TIER_SLA_MINUTES: dict[CustomerTier, int] = {
    CustomerTier.FREE: 480,       # 8 hours
    CustomerTier.BASIC: 240,      # 4 hours
    CustomerTier.PREMIUM: 60,     # 1 hour
    CustomerTier.ENTERPRISE: 15,  # 15 minutes
}


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[str | None] = mapped_column(String(300))
    tier: Mapped[CustomerTier] = mapped_column(
        String(20), default=CustomerTier.FREE, nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(String(100), index=True, default=None)

    # Relationships
    tickets = relationship("Ticket", back_populates="customer", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Customer {self.name} [{self.tier.value}]>"
