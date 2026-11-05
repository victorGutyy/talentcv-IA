import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TOKEN = "token-de-prueba"


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "datos", token=TOKEN)


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": TOKEN}) as c:
        yield c
    app.state.engine.dispose()
