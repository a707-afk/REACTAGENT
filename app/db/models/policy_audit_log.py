"""Policy audit log: immutable record for all policy decisions.

This table MUST NOT be deletable through normal business APIs.
Only admins can archive old entries.
"""
from __future__ import annotations

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, Base


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _new_uuid():
    import uuid
    return str(uuid.uuid4())


class PolicyAuditLog(Base):
    __tablename__ = "policy_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )  # intercept | allow | deny | approval | hitl_request
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    detail_json: Mapped[str | None] = mapped_column(Text)  # JSON with full context
    risk_level: Mapped[str | None] = mapped_column(String(20))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True,
    )

    def __repr__(self) -> str:
        return f"<PolicyAuditLog {self.id[:8]} [{self.event_type}] {self.action}>"
