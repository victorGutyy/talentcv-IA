import pytest
from fastapi.testclient import TestClient

from app.ai.fake import FakeProvider
from app.core.config import Settings
from app.main import create_app

TOKEN = "token-de-prueba"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "datos", token=TOKEN)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def client(settings, provider):
    app = create_app(settings, provider=provider)
    with TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": TOKEN}) as c:
        yield c
    app.state.engine.dispose()
