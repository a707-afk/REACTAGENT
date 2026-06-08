"""ChatSession and Message models for multi-turn conversation memory."""
from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, Base


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    ticket_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="SET NULL"), index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum"),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    messages = relationship(
        "Message", back_populates="session", lazy="selectin",
        order_by="Message.created_at", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.id[:8]} [{self.status.value}]>"


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citations_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grounding_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.id[:8]} [{self.role.value}] {self.content[:40]}>"
