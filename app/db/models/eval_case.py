"""EvalCase model: a single gold-standard evaluation case with results."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Gold standard data
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="faq",
        comment="faq | pdf_table | policy | no_answer | security | multi_turn",
    )
    gold_document_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of gold document IDs",
    )
    gold_chunk_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of gold chunk IDs",
    )
    answer_facts: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of expected answer facts",
    )
    forbidden_document_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of documents that MUST NOT appear",
    )
    roles: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="Comma-separated roles for access control",
    )

    # Evaluation results (computed)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | passed | failed | error",
    )
    recall_at_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr_at_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndcg_at_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    unauthorized_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_unsupported_sentences: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gate_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retrieved chunk IDs (for debugging)
    retrieved_chunk_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of retrieved chunk IDs",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    eval_run = relationship("EvalRun", back_populates="cases", lazy="selectin")

    def __repr__(self) -> str:
        return f"<EvalCase {self.case_id} status={self.status}>"
