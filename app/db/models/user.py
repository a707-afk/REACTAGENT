"""User and API Key models for authentication and authorization."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, Base


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    username: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(300))
    password_hash: Mapped[str | None] = mapped_column(String(256))
    roles_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of roles
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of scopes
    department: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", lazy="selectin",
                            cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.id[:8]} [{self.username}]>"


class ApiKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Store SHA-256 hash, never plaintext
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # for display
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer, default=None)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new API key. Returns (raw_key, key_hash)."""
        raw = f"ek_{secrets.token_urlsafe(32)}"
        return raw, ApiKey.hash_key(raw)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<ApiKey {self.key_prefix}... [{self.name}]>"
