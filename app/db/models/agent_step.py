"""AgentStep model: a single step in an agent execution with full observability."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="execute",
        comment="plan | execute | observe | evaluate | approve | finalize",
    )

    # Input / Output (JSON)
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tool execution (if step_type=execute)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Permission
    permission_check: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="allowed | denied | needs_approval",
    )
    permission_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Performance
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Errors
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("AgentRun", back_populates="steps", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AgentStep {self.step_index} type={self.step_type} tool={self.tool_name}>"
