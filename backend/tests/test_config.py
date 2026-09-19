from pathlib import Path

import pytest
import yaml

from app.core.config import Settings


def test_live_requires_secrets():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_mode="live")


def test_compose_and_env_match_local_defaults():
    root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8-sig"))
    services = compose["services"]
    assert services["frontend"]["ports"] == ["127.0.0.1:5173:80"]
    assert services["backend"]["volumes"] == ["decidr-data:/app/data"]
    for service in services.values():
        assert (root / service["build"] / "Dockerfile").exists()
    defaults = Settings(_env_file=root / ".env.example")
    assert defaults.app_mode == "demo" and defaults.frontend_url == "http://localhost:5173"
