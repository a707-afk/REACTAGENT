"""Document model: represents an uploaded document with metadata and status."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    # ── Columns ─────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="File size in bytes")
    content_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False,
        comment="SHA-256 hash for dedup",
    )

    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft | active | archived | deleted",
    )

    # Parsed metadata
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="Detected language: zh, en, de, etc.")
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    security_level: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    allowed_roles: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Comma-separated roles")

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    jobs = relationship(
        "IngestionJob", back_populates="document", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document {self.id} file={self.file_name} status={self.status}>"
