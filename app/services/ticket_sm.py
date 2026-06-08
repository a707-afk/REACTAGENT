"""Ticket state machine: enforces valid transitions with audit trail."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models.ticket import (
    VALID_TRANSITIONS,
    TicketPriority,
    TicketStatus,
    can_transition,
)
from app.db.models.customer import CustomerTier, TIER_SLA_MINUTES

logger = logging.getLogger(__name__)


@dataclass
class TicketStateMachine:
    """Pure-logic state machine — does NOT touch the DB directly."""

    ticket_id: str
    current_status: TicketStatus
    priority: TicketPriority
    customer_tier: CustomerTier | None = None

    audit: list[dict[str, Any]] = field(default_factory=list)

    TRANSITIONS = VALID_TRANSITIONS

    def transition(self, target: TicketStatus, *, reason: str = "") -> bool:
        if not can_transition(self.current_status, target):
            logger.warning(
                "Invalid transition: %s -> %s (ticket %s)",
                self.current_status.value,
                target.value,
                self.ticket_id,
            )
            self.audit.append({
                "from": self.current_status.value,
                "to": target.value,
                "allowed": False,
                "reason": reason or "invalid transition",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return False

        self.audit.append({
            "from": self.current_status.value,
            "to": target.value,
            "allowed": True,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        self.current_status = target
        return True

    def compute_sla_deadline(self) -> datetime | None:
        """Return SLA deadline based on priority + customer tier."""
        base_minutes = {
            TicketPriority.P0_CRITICAL: 15,
            TicketPriority.P1_HIGH: 60,
            TicketPriority.P2_MEDIUM: 240,
            TicketPriority.P3_LOW: 480,
        }
        minutes = base_minutes.get(self.priority, 240)
        if self.customer_tier:
            tier_fraction = TIER_SLA_MINUTES.get(self.customer_tier, 480) / 480.0
            minutes = max(5, int(minutes * tier_fraction))
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def can_auto_close(self, resolved_at: datetime | None, idle_hours: int = 72) -> bool:
        """Check if a resolved ticket can be auto-closed after idle period."""
        if self.current_status != TicketStatus.RESOLVED:
            return False
        if resolved_at is None:
            return False
        return datetime.now(timezone.utc) - resolved_at > timedelta(hours=idle_hours)
