import pytest

BASE = {"nombre_completo": "María Fernanda Orozco"}


def crear(client, **extra):
    r = client.post("/api/perfiles", json={**BASE, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_y_obtener(client):
    p = crear(
        client,
        titular="Ingeniera de sistemas",
        email="mf@example.com",
        telefono="+57 300 000 0000",
        enlaces=[{"etiqueta": "GitHub", "url": "https://github.com/ejemplo"}],
    )
    assert len(p["id"]) == 32
    r = client.get(f"/api/perfiles/{p['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == "mf@example.com"
    assert r.json()["enlaces"][0]["etiqueta"] == "GitHub"
    assert r.json()["creado_en"].endswith("Z") or "+00:00" in r.json()["creado_en"]


def test_listar_ordenado_por_actualizacion(client):
    a = crear(client, nombre_completo="Ana")
    b = crear(client, nombre_completo="Beto")
    client.put(f"/api/perfiles/{a['id']}", json={"nombre_completo": "Ana Editada"})
    nombres = [x["nombre_completo"] for x in client.get("/api/perfiles").json()]
    assert nombres == ["Ana Editada", "Beto"]
    assert b["id"] in [x["id"] for x in client.get("/api/perfiles").json()]


def test_actualizar(client):
    p = crear(client, ciudad="Bogotá")
    r = client.put(f"/api/perfiles/{p['id']}", json={"nombre_completo": "Nuevo Nombre", "pais": "Colombia"})
    assert r.status_code == 200
    d = r.json()
    assert d["nombre_completo"] == "Nuevo Nombre" and d["pais"] == "Colombia"
    assert d["ciudad"] is None  # PUT reemplaza: lo no enviado se borra
    assert d["creado_en"] == p["creado_en"]


def test_duplicar(client):
    p = crear(client, titular="Dev", enlaces=[{"etiqueta": "Web", "url": "https://ejemplo.org"}])
    r = client.post(f"/api/perfiles/{p['id']}/duplicar")
    assert r.status_code == 201
    c = r.json()
    assert c["id"] != p["id"]
    assert c["nombre_completo"].endswith("(copia)")
    assert c["titular"] == "Dev" and c["enlaces"] == p["enlaces"]
    assert len(client.get("/api/perfiles").json()) == 2


def test_eliminar(client):
    p = crear(client)
    assert client.delete(f"/api/perfiles/{p['id']}").status_code == 204
    assert client.get(f"/api/perfiles/{p['id']}").status_code == 404
    assert client.delete(f"/api/perfiles/{p['id']}").status_code == 404
    assert client.get("/api/perfiles").json() == []


def test_inexistente_404(client):
    assert client.get("/api/perfiles/noexiste").status_code == 404
    assert client.put("/api/perfiles/noexiste", json=BASE).status_code == 404
    assert client.post("/api/perfiles/noexiste/duplicar").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"nombre_completo": ""},
        {"nombre_completo": "   "},
        {},
        {**BASE, "email": "no-es-correo"},
        {**BASE, "telefono": "abc"},
        {**BASE, "enlaces": [{"etiqueta": "x", "url": "javascript:alert(1)"}]},
        {**BASE, "enlaces": [{"etiqueta": "x", "url": "ftp://ejemplo.org"}]},
        {**BASE, "enlaces": [{"etiqueta": "x", "url": "https://e.org"}] * 11},
        {**BASE, "resumen": "x" * 2001},
        {"nombre_completo": "x" * 201},
    ],
)
def test_validacion_rechaza(client, payload):
    assert client.post("/api/perfiles", json=payload).status_code == 422


def test_limpia_espacios_y_vacios(client):
    p = crear(client, nombre_completo="  Luis  ", titular="   ", email=" l@x.co ")
    assert p["nombre_completo"] == "Luis"
    assert p["titular"] is None
    assert p["email"] == "l@x.co"


def test_persiste_tras_reiniciar(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    h = {"x-tcv-token": settings.token}
    app1 = create_app(settings)
    with TestClient(app1, base_url="http://127.0.0.1", headers=h) as c:
        pid = c.post("/api/perfiles", json=BASE).json()["id"]
    app1.state.engine.dispose()

    app2 = create_app(settings)
    with TestClient(app2, base_url="http://127.0.0.1", headers=h) as c:
        assert c.get(f"/api/perfiles/{pid}").json()["nombre_completo"] == BASE["nombre_completo"]
    app2.state.engine.dispose()
