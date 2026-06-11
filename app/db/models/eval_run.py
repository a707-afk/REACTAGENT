"""EvalRun model: records an evaluation run with config and metrics."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    eval_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rag",
        comment="rag | agent | multimodal | security",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued",
        comment="queued | running | completed | failed",
    )
    config_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON config: thresholds, retriever params, etc.",
    )

    # Metrics (computed after evaluation)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recall_at_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr_at_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndcg_at_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    unsupported_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    unauthorized_in_topk: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refusal_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    gate_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    cases = relationship("EvalCase", back_populates="eval_run", lazy="selectin", cascade="all, delete-orphan")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<EvalRun {self.id} type={self.eval_type} status={self.status}>"
