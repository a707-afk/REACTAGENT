"""Tenant model for multi-tenancy isolation."""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, Base


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text)  # tenant-specific settings
    max_users: Mapped[int | None] = mapped_column(default=None)
    max_documents: Mapped[int | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"<Tenant {self.id[:8]} [{self.name}]>"
