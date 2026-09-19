from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_mode: Literal["demo", "live"] = "demo"
    database_url: str = "sqlite:///./data/decidr.db"
    frontend_url: str = "http://localhost:5173"
    app_password: str = ""
    session_secret: str = "demo-only-change-before-live-use"
    cookie_secure: bool = False
    token_encryption_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/oauth/gmail/callback"
    known_senders: str = ""
    max_amount: float = Field(default=1000, gt=0)
    allowed_currency: str = "PLN"
    min_confidence: float = Field(default=0.9, ge=0, le=1)
    sync_interval_seconds: int = Field(default=120, ge=30)
    gmail_query: str = "in:inbox newer_than:7d -from:me"
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
    scheduler_enabled: bool = True
    demo_autoload: bool = True

    @model_validator(mode="after")
    def validate_live(self):
        if self.app_mode == "live":
            if len(self.app_password) < 12 or len(self.session_secret) < 32:
                raise ValueError("Live requires APP_PASSWORD (12+ chars) and SESSION_SECRET (32+ chars).")
            if not self.token_encryption_key:
                raise ValueError("Live requires TOKEN_ENCRYPTION_KEY (Fernet key).")
            from cryptography.fernet import Fernet

            Fernet(self.token_encryption_key.encode())
        return self

    @property
    def senders(self) -> set[str]:
        return {s.strip().lower() for s in self.known_senders.split(",") if s.strip()}

    @property
    def gmail_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)

    def ensure_data_dir(self):
        if self.database_url.startswith("sqlite:///") and ":memory:" not in self.database_url:
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
