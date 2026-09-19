from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StrictBool, computed_field, field_validator


class Analysis(BaseModel):
    classification: Literal["needs_reply", "needs_review", "skip"]
    decision_type: Literal["purchase", "invoice", "schedule", "routine", "other"]
    sender_name: str
    summary: str
    request_text: str
    push_text: str = ""
    amount: float | None = None
    currency: str | None = None
    deadline: str | None = None
    conditions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)
    is_binary: bool = True
    draft: str = ""

    @field_validator("amount")
    @classmethod
    def finite_amount(cls, value):
        import math

        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("Amount must be a finite, nonnegative number")
        return value


class NormalizedMessage(BaseModel):
    gmail_message_id: str
    gmail_thread_id: str
    rfc_message_id: str | None
    references: str = ""
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    body: str
    has_attachments: bool = False
    normalization_flags: list[str] = Field(default_factory=list)


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    gmail_message_id: str
    gmail_thread_id: str
    rfc_message_id: str | None
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    original_body: str
    summary: str
    request_text: str
    decision_type: str
    amount: float | None
    currency: str | None
    deadline: str | None
    conditions: list[str]
    missing_fields: list[str]
    risk_flags: list[str]
    safety_reasons: list[str]
    confidence: float
    classification: str
    status: str
    user_choice: str | None
    draft: str | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    send_attempted_at: datetime | None
    send_error: str | None
    version: int

    @computed_field
    @property
    def needs_decision(self) -> bool:
        return self.classification != "skip"

    @computed_field
    @property
    def is_binary(self) -> bool:
        return self.classification == "needs_reply"

    @field_validator("received_at", "created_at", "updated_at", "sent_at", "send_attempted_at")
    @classmethod
    def restore_utc(cls, value):
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class ChoiceIn(BaseModel):
    choice: Literal["approve", "reject"]
    version: int = Field(ge=1)


class DraftIn(BaseModel):
    draft: str = Field(min_length=1, max_length=5000)
    version: int = Field(ge=1)

    @field_validator("draft")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Draft must not be blank")
        return value.strip()


class SendIn(BaseModel):
    confirmed: StrictBool
    version: int = Field(ge=1)

    @field_validator("confirmed")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmed: true is required")
        return value


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class PushIn(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def public_push_provider(cls, value):
        url = urlparse(value)
        host = url.hostname or ""
        allowed = (
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
            "web.push.apple.com",
            "notify.windows.com",
        )
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.port not in (None, 443)
            or not any(host == domain or host.endswith("." + domain) for domain in allowed)
        ):
            raise ValueError("Unsupported Web Push provider")
        return value
