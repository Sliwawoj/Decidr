from pathlib import Path
from typing import Literal

from pydantic import model_validator
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
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/oauth/gmail/callback"
    sync_interval_seconds: int = 120
    gmail_query: str = "in:inbox -from:me"
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
    def gmail_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)

    def ensure_data_dir(self):
        if self.database_url.startswith("sqlite:///") and ":memory:" not in self.database_url:
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
