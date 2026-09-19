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
        app_mode="demo",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app, headers={"X-Decidr-Client": "web"}) as client:
        yield client
