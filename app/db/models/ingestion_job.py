"""IngestionJob model: tracks async document ingestion tasks."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    # ── Columns ─────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id"), index=True, nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued",
        comment="queued | running | completed | failed",
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ingest_document",
        comment="ingest_document | run_eval | process_agent_job",
    )
    task_params: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON-encoded params")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document = relationship("Document", back_populates="jobs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<IngestionJob {self.id} status={self.status} progress={self.progress}>"
