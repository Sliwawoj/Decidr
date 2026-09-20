import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        scheduler_enabled=False,
        app_mode="live",
        app_password="test-password-123",
        session_secret="1234567890abcdef1234567890abcdef",
        token_encryption_key="yfvgCg-aPAcQRD68MigiuhnnE__cFywdjIwvAOt4tOk=",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app, headers={"X-Decidr-Client": "web"}) as client:
        login = client.post("/api/session", json={"password": settings.app_password})
        assert login.status_code == 200
        yield client
