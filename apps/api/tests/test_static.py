from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _app(tmp_path, token="t"):
    web = tmp_path / "web"
    (web / "perfil").mkdir(parents=True)
    (web / "index.html").write_text("<html>inicio</html>", encoding="utf-8")
    (web / "perfil" / "index.html").write_text("<html>perfil</html>", encoding="utf-8")
    s = Settings(data_dir=tmp_path / "datos", token=token, web_dir=web)
    return create_app(s)


def test_sirve_la_interfaz_sin_token(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert "inicio" in c.get("/").text
        assert "perfil" in c.get("/perfil/").text
    app.state.engine.dispose()


def test_la_interfaz_no_tapa_ni_abre_el_api(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/perfiles").status_code == 401  # el token sigue siendo obligatorio
        assert c.get("/api/perfiles", headers={"x-tcv-token": "t"}).status_code == 200
    app.state.engine.dispose()


def test_la_interfaz_tambien_exige_host_local(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url="http://evil.example.com") as c:
        assert c.get("/").status_code == 403
    app.state.engine.dispose()


def test_sin_web_dir_no_hay_interfaz(settings):
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/").status_code == 404
    app.state.engine.dispose()


def test_cors_solo_con_origenes_de_desarrollo(tmp_path):
    s = Settings(data_dir=tmp_path / "d", token="t", dev_origins=("http://localhost:3000",))
    app = create_app(s)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        ok = c.options(
            "/api/perfiles",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-tcv-token",
            },
        )
        assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
        otro = c.options(
            "/api/perfiles",
            headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in otro.headers
    app.state.engine.dispose()
