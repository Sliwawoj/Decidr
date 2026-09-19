from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    gmail_message_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String)
    rfc_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    references: Mapped[str] = mapped_column(Text, default="")
    sender_name: Mapped[str] = mapped_column(String)
    sender_email: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    original_body: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    request_text: Mapped[str] = mapped_column(Text)
    decision_type: Mapped[str] = mapped_column(String)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    deadline: Mapped[str | None] = mapped_column(String, nullable=True)
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list)
    safety_reasons: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="analyzed", index=True)
    user_choice: Mapped[str | None] = mapped_column(String, nullable=True)
    draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_reply_id: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    keys: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GmailConnection(Base):
    __tablename__ = "gmail_connection"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String)
    # Only messages received at/after this moment are analyzed (no mailbox backfill).
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
