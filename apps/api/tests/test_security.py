from fastapi.testclient import TestClient

from app.main import create_app


def test_api_sin_token_es_401(settings):
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/estado").status_code == 401
        assert c.get("/api/perfiles").status_code == 401
    app.state.engine.dispose()


def test_token_incorrecto_es_401(settings):
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": "otro"}) as c:
        assert c.get("/api/estado").status_code == 401
    app.state.engine.dispose()


def test_con_token_pasa(client):
    r = client.get("/api/estado")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_host_ajeno_es_403(settings):
    app = create_app(settings)
    with TestClient(app, base_url="http://evil.example.com", headers={"x-tcv-token": settings.token}) as c:
        assert c.get("/api/estado").status_code == 403
    app.state.engine.dispose()


def test_sin_token_configurado_todo_se_rechaza(tmp_path):
    from app.core.config import Settings

    s = Settings(data_dir=tmp_path / "d", token="")
    app = create_app(s)
    with TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": ""}) as c:
        assert c.get("/api/estado").status_code == 401
    app.state.engine.dispose()
