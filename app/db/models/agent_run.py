"""AgentRun model: tracks a full agent execution with complete audit trail."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="running | waiting_approval | completed | failed | terminated",
    )
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low",
        comment="low | medium | high | critical",
    )

    # Structured plan
    plan_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of plan steps")
    current_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Budget tracking
    budget_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment='JSON: {"max_steps": 10, "max_tool_calls": 20, "max_latency_ms": 120000}',
    )

    # Outcomes
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    termination_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Metrics
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    permission_deny_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Audit
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of errors")
    approvals_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of approval records")
    audit_trace_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of audit entries")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    steps = relationship("AgentStep", back_populates="run", lazy="selectin",
                          order_by="AgentStep.step_index", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AgentRun {self.id} status={self.status} risk={self.risk_level}>"
