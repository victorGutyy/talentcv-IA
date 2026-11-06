import json
import time

from fastapi.testclient import TestClient

from app.ai.fake import FakeProvider
from app.core.db import migrate
from app.main import create_app
from app.orchestrator.models import Job

BUENA = json.dumps(
    {"nombre": "Laura Méndez Ríos", "cargo": "Desarrolladora", "anio_inicio": 2020, "fecha_graduacion": None}
)
INVENTA = json.dumps(
    {
        "nombre": "Laura Méndez Ríos",
        "cargo": "Desarrolladora",
        "anio_inicio": 2020,
        "fecha_graduacion": "2018",
    }
)


def esperar(client, job_id, estados, timeout=5.0):
    fin = time.time() + timeout
    while time.time() < fin:
        j = client.get(f"/api/tareas/{job_id}").json()
        if j["estado"] in estados:
            return j
        time.sleep(0.02)
    raise AssertionError(f"la tarea no llego a {estados}: {j}")


def lanzar(client, tipo="diagnostico_ia"):
    r = client.post("/api/tareas", json={"tipo": tipo})
    assert r.status_code == 202, r.text
    return r.json()


def app_con(settings, provider):
    app = create_app(settings, provider=provider)
    return app, TestClient(app, base_url="http://127.0.0.1", headers={"x-tcv-token": settings.token})


def test_diagnostico_completa_con_resultado(settings):
    app, c = app_con(settings, FakeProvider([BUENA]))
    with c:
        j = esperar(c, lanzar(c)["id"], {"completado", "error"})
    app.state.engine.dispose()
    assert j["estado"] == "completado" and j["progreso"] == 1.0
    assert j["resultado"]["ok"] is True
    assert j["resultado"]["verificaciones"]["no_inventa_la_fecha_de_graduacion"] is True
    assert j["iniciada_en"] and j["terminada_en"]


def test_diagnostico_detecta_datos_inventados(settings):
    app, c = app_con(settings, FakeProvider([INVENTA]))
    with c:
        j = esperar(c, lanzar(c)["id"], {"completado", "error"})
    app.state.engine.dispose()
    assert j["estado"] == "completado"
    assert j["resultado"]["ok"] is False
    assert j["resultado"]["verificaciones"]["no_inventa_la_fecha_de_graduacion"] is False


def test_el_documento_de_prueba_va_delimitado_como_no_confiable(settings):
    prov = FakeProvider([BUENA])
    app, c = app_con(settings, prov)
    with c:
        esperar(c, lanzar(c)["id"], {"completado", "error"})
    app.state.engine.dispose()
    assert "DOCUMENTO_NO_CONFIABLE_" in prov.calls[0]["prompt"]
    assert "No inventes" in prov.calls[0]["system"]
    assert prov.calls[0]["schema"] is not None


def test_motor_apagado_termina_en_error_claro(settings):
    app, c = app_con(settings, FakeProvider(available=False))
    with c:
        j = esperar(c, lanzar(c)["id"], {"completado", "error"})
    app.state.engine.dispose()
    assert j["estado"] == "error" and "no disponible" in j["error"]


def test_salida_invalida_del_modelo_es_error(settings):
    app, c = app_con(settings, FakeProvider(["no es json"]))
    with c:
        j = esperar(c, lanzar(c)["id"], {"completado", "error"})
    app.state.engine.dispose()
    assert j["estado"] == "error" and "salida válida" in j["error"]


def test_cancelar_una_tarea_en_curso(settings):
    app, c = app_con(settings, FakeProvider([BUENA], token_delay=0.05, tokens=200))
    with c:
        job = lanzar(c)
        esperar(c, job["id"], {"ejecutando"})
        r = c.post(f"/api/tareas/{job['id']}/cancelar")
        assert r.status_code == 200
        j = esperar(c, job["id"], {"cancelado"})
    app.state.engine.dispose()
    assert j["estado"] == "cancelado" and j["resultado"] is None


def test_solo_una_tarea_de_ia_a_la_vez(settings):
    app, c = app_con(settings, FakeProvider([BUENA], token_delay=0.05, tokens=40))
    with c:
        a, b = lanzar(c), lanzar(c)
        esperar(c, a["id"], {"ejecutando"})
        assert c.get(f"/api/tareas/{b['id']}").json()["estado"] == "en_cola"
        esperar(c, a["id"], {"completado"}, timeout=10)
        esperar(c, b["id"], {"completado"}, timeout=10)
    app.state.engine.dispose()


def test_progreso_intermedio_visible(settings):
    app, c = app_con(settings, FakeProvider([BUENA], token_delay=0.05, tokens=60))
    with c:
        job = lanzar(c)
        esperar(c, job["id"], {"ejecutando"})
        visto = []
        fin = time.time() + 5
        while time.time() < fin:
            j = c.get(f"/api/tareas/{job['id']}").json()
            visto.append(j["progreso"])
            if j["estado"] != "ejecutando":
                break
            time.sleep(0.1)
    app.state.engine.dispose()
    assert any(0.1 < p < 1.0 for p in visto)
    assert visto == sorted(visto)


def test_tipo_desconocido_422_y_tarea_inexistente_404(client):
    assert client.post("/api/tareas", json={"tipo": "borrar_todo"}).status_code == 422
    assert client.get("/api/tareas/noexiste").status_code == 404
    assert client.post("/api/tareas/noexiste/cancelar").status_code == 404


def test_tareas_requieren_token(settings):
    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/tareas").status_code == 401
        assert c.post("/api/tareas", json={"tipo": "diagnostico_ia"}).status_code == 401
        assert c.get("/api/ia/estado").status_code == 401
    app.state.engine.dispose()


def test_estado_ia(client):
    d = client.get("/api/ia/estado").json()
    assert d["disponible"] and d["modelo_instalado"] and d["proveedor"] == "fake"


def test_listado_reciente(client):
    for _ in range(3):
        lanzar(client)
    assert len(client.get("/api/tareas").json()) == 3


def test_tareas_activas_quedan_interrumpidas_al_reiniciar(settings):
    migrate(settings)
    app1 = create_app(settings, provider=FakeProvider(), run_migrations=False)
    sf = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=app1.state.engine)
    with sf() as db:
        db.add(Job(id="a" * 32, kind="diagnostico_ia", status="ejecutando"))
        db.add(Job(id="b" * 32, kind="diagnostico_ia", status="en_cola"))
        db.add(Job(id="c" * 32, kind="diagnostico_ia", status="completado"))
        db.commit()
    app1.state.engine.dispose()

    app2, c = app_con(settings, FakeProvider())
    with c:
        estados = {j["id"][0]: j["estado"] for j in c.get("/api/tareas").json()}
    app2.state.engine.dispose()
    assert estados == {"a": "interrumpido", "b": "interrumpido", "c": "completado"}
