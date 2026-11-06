import time

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

FIN = {"completado", "error", "cancelado", "interrumpido"}


def esperar(client, job_id, estados=FIN, timeout=30.0):
    fin = time.time() + timeout
    j = {}
    while time.time() < fin:
        j = client.get(f"/api/tareas/{job_id}").json()
        if j["estado"] in estados:
            return j
        time.sleep(0.03)
    raise AssertionError(f"la tarea no llego a {estados}: {j}")


def app_client(settings: Settings, provider):
    app = create_app(settings, provider=provider)
    client = TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": settings.token})
    return app, client


def crear_perfil(client, nombre="Laura Méndez Ríos") -> str:
    r = client.post("/api/perfiles", json={"nombre_completo": nombre})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def subir(client, perfil_id, data: bytes, nombre="cv.pdf", **kw):
    return client.post(
        f"/api/perfiles/{perfil_id}/documentos",
        params={"nombre": nombre},
        content=data,
        headers={"content-type": "application/octet-stream"},
        **kw,
    )
