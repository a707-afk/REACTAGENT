"""Tool call audit: every Agent tool execution with params, result, and permission."""
from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, Base


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _new_uuid():
    import uuid
    return str(uuid.uuid4())


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    run_id: Mapped[str | None] = mapped_column(
        String(36), index=True,
    )  # FK to agent_runs if applicable
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    params_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    permission_result: Mapped[str | None] = mapped_column(String(20))  # allowed|denied|needs_approval
    permission_reason: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str | None] = mapped_column(String(64), index=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True,
    )

    def __repr__(self) -> str:
        return f"<ToolCall {self.id[:8]} [{self.tool_name}] ok={self.success}>"
