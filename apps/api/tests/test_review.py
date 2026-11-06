import json
import sqlite3

import pytest
from alembic import command

from app.ai.fake import FakeProvider
from app.core.db import _alembic_config, migrate
from tests import docfactory as df
from tests.helpers import app_client, crear_perfil, esperar, subir
from tests.test_extraction import BUENA, extraer, hechos, montar, respuesta  # noqa: F401


@pytest.fixture
def con_hechos(montar):  # noqa: F811
    app, c, pid, doc = montar(FakeProvider([BUENA]))
    extraer(c, doc)
    return app, c, pid, doc


def uno(c, pid, categoria, **filtros):
    return next(h for h in hechos(c, pid, **filtros) if h["category"] == categoria)


def accion(c, fact_id, accion, datos=None):
    return c.patch(f"/api/hechos/{fact_id}", json={"accion": accion, "datos": datos})


def campos_con_error(r) -> set[str]:
    return {e["loc"][1] for e in r.json()["detail"]}


# ------------------------------------------------------------------ transiciones
def test_confirmar_rechazar_y_restaurar(con_hechos):
    _, c, pid, _ = con_hechos
    h = uno(c, pid, "educacion")
    assert h["status"] == "pendiente"
    assert accion(c, h["id"], "confirmar").json()["status"] == "confirmado"
    assert accion(c, h["id"], "rechazar").json()["status"] == "rechazado"
    assert accion(c, h["id"], "restaurar").json()["status"] == "pendiente"


def test_solo_lo_aprobado_se_lista_como_aprobado(con_hechos):
    _, c, pid, _ = con_hechos
    a, b, rechazado = (uno(c, pid, k) for k in ("educacion", "idioma", "certificacion"))
    accion(c, a["id"], "confirmar")
    accion(c, b["id"], "editar", {"idioma": "Inglés", "nivel": "B2"})
    accion(c, rechazado["id"], "rechazar")
    aprobados = hechos(c, pid, estado="confirmado,editado")
    assert {h["id"] for h in aprobados} == {a["id"], b["id"]}
    assert {h["id"] for h in hechos(c, pid, estado="rechazado")} == {rechazado["id"]}
    assert len(hechos(c, pid, estado="pendiente")) == len(hechos(c, pid)) - 3


def test_estado_invalido_422_y_dato_inexistente_404(con_hechos):
    _, c, pid, _ = con_hechos
    assert c.get(f"/api/perfiles/{pid}/hechos", params={"estado": "aprobado"}).status_code == 422
    assert accion(c, "noexiste", "confirmar").status_code == 404
    assert c.patch("/api/hechos/x", json={"accion": "borrar_todo"}).status_code == 422


# ------------------------------------------------------------------ edicion
def test_editar_corrige_el_ocr_y_conserva_el_original(con_hechos):
    _, c, pid, _ = con_hechos
    h = uno(c, pid, "educacion")
    original = dict(h["data"])
    r = accion(
        c,
        h["id"],
        "editar",
        {
            "titulo": "Ingeniería Informática",
            "institucion": "Universidad del Norte",
            "fecha_graduacion": "2019",
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "editado" and d["data"]["fecha_graduacion"] == "2019"
    assert d["original_data"] == original  # lo que extrajo el sistema queda registrado
    assert d["quote"] == h["quote"] and d["page"] == h["page"]  # la fuente original se conserva
    # una segunda edicion no pisa el original
    d2 = accion(c, h["id"], "editar", {"titulo": "Ingeniería de Sistemas", "institucion": None}).json()
    assert d2["original_data"] == original
    assert d2["data"] == {"titulo": "Ingeniería de Sistemas", "institucion": None, "fecha_graduacion": None}
    # confirmar un dato editado no borra que fue editado
    assert accion(c, h["id"], "confirmar").json()["status"] == "editado"


def test_editar_limpia_los_avisos_de_campos_descartados(con_hechos):
    _, c, pid, _ = con_hechos
    h = uno(c, pid, "educacion")
    h2 = accion(
        c, h["id"], "editar", {"titulo": "X título", "institucion": None, "fecha_graduacion": None}
    ).json()
    assert h2["dropped_fields"] == []


@pytest.mark.parametrize(
    ("categoria", "datos", "campo"),
    [
        ("experiencia", {"cargo": "", "empresa": "X"}, "cargo"),
        ("experiencia", {"cargo": "   "}, "cargo"),
        ("experiencia", {"cargo": "A" * 301}, "cargo"),
        ("experiencia", {"cargo": "Dev", "salario": "mucho"}, "salario"),
        ("experiencia", {"cargo": 5}, "cargo"),
        ("experiencia", {"cargo": "Dev", "empresa": ["x"]}, "empresa"),
        ("contacto", {"tipo": "fax", "valor": "123"}, "tipo"),
        ("contacto", {"tipo": "email", "valor": ""}, "valor"),
        ("habilidad", {"nombres": []}, "nombres"),
        ("habilidad", {"nombres": ["x"] * 41}, "nombres"),
        ("habilidad", {"nombres": ["y" * 61]}, "nombres"),
        ("logro", {"texto": "z" * 601}, "texto"),
    ],
)
def test_validacion_de_datos_editados(con_hechos, categoria, datos, campo):
    _, c, pid, _ = con_hechos
    h = uno(c, pid, categoria)
    antes = h["data"]
    r = accion(c, h["id"], "editar", datos)
    assert r.status_code == 422 and campo in campos_con_error(r), r.text
    assert uno(c, pid, categoria)["data"] == antes and uno(c, pid, categoria)["status"] == "pendiente"


def test_editar_habilidades_y_logro(con_hechos):
    _, c, pid, _ = con_hechos
    h = uno(c, pid, "habilidad")
    r = accion(c, h["id"], "editar", {"nombres": [" Python ", "", "SQL"]})
    assert r.json()["data"]["nombres"] == ["Python", "SQL"]


# ------------------------------------------------------------------ datos propios
def test_dato_propio_nace_confirmado_sin_cita(con_hechos):
    _, c, pid, _ = con_hechos
    r = c.post(
        f"/api/perfiles/{pid}/hechos",
        json={
            "categoria": "certificacion",
            "datos": {"nombre": "Curso de liderazgo", "emisor": "Mi empresa"},
        },
    )
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "confirmado" and d["origin"] == "manual"
    assert d["document_id"] is None and d["quote"] == "" and d["page"] is None
    assert d["data"] == {"nombre": "Curso de liderazgo", "emisor": "Mi empresa", "fecha": None}
    # editar un dato propio lo deja confirmado y sin 'original'
    e = accion(c, d["id"], "editar", {"nombre": "Curso de liderazgo avanzado"}).json()
    assert e["status"] == "confirmado" and e["original_data"] is None


@pytest.mark.parametrize(
    ("categoria", "datos", "campo"),
    [("experiencia", {}, "cargo"), ("idioma", {"idioma": ""}, "idioma"), ("nada", {"x": "y"}, "categoria")],
)
def test_dato_propio_invalido(con_hechos, categoria, datos, campo):
    _, c, pid, _ = con_hechos
    r = c.post(f"/api/perfiles/{pid}/hechos", json={"categoria": categoria, "datos": datos})
    assert r.status_code == 422 and campo in campos_con_error(r)


def test_dato_propio_en_perfil_inexistente(con_hechos):
    _, c, _, _ = con_hechos
    r = c.post("/api/perfiles/noexiste/hechos", json={"categoria": "idioma", "datos": {"idioma": "Francés"}})
    assert r.status_code == 404


# ------------------------------------------------------------------ lote
def test_lote_confirma_solo_lo_seleccionado(con_hechos):
    _, c, pid, _ = con_hechos
    todos = hechos(c, pid)
    elegidos = [h["id"] for h in todos[:3]]
    r = c.post(f"/api/perfiles/{pid}/hechos/lote", json={"ids": elegidos, "accion": "confirmar"})
    assert r.json() == {"actualizados": 3, "ignorados": 0}
    estados = {h["id"]: h["status"] for h in hechos(c, pid)}
    assert [estados[i] for i in elegidos] == ["confirmado"] * 3
    assert sum(1 for s in estados.values() if s == "pendiente") == len(todos) - 3


def test_lote_ignora_ids_de_otro_perfil_y_ids_inexistentes(con_hechos):
    _, c, pid, _ = con_hechos
    otro = crear_perfil(c, "Otra Persona")
    ajeno = c.post(
        f"/api/perfiles/{otro}/hechos", json={"categoria": "idioma", "datos": {"idioma": "Francés"}}
    ).json()
    propio = uno(c, pid, "educacion")
    r = c.post(
        f"/api/perfiles/{pid}/hechos/lote",
        json={"ids": [propio["id"], ajeno["id"], "inventado"], "accion": "rechazar"},
    )
    assert r.json() == {"actualizados": 1, "ignorados": 2}
    assert hechos(c, otro)[0]["status"] == "confirmado"  # el ajeno no se tocó


def test_lote_valida_la_entrada(con_hechos):
    _, c, pid, _ = con_hechos
    url = f"/api/perfiles/{pid}/hechos/lote"
    assert c.post(url, json={"ids": [], "accion": "confirmar"}).status_code == 422
    assert c.post(url, json={"ids": ["a"], "accion": "editar"}).status_code == 422
    assert (
        c.post("/api/perfiles/noexiste/hechos/lote", json={"ids": ["a"], "accion": "confirmar"}).status_code
        == 404
    )


# ------------------------------------------------------------------ interaccion con la extraccion
def test_reextraer_no_resucita_rechazados_ni_valores_editados(con_hechos):
    _, c, pid, doc = con_hechos
    rechazado = uno(c, pid, "certificacion")
    editado = uno(c, pid, "educacion")
    accion(c, rechazado["id"], "rechazar")
    accion(c, editado["id"], "editar", {"titulo": "Ingeniería en Informática", "institucion": "U. del Norte"})
    extraer(c, doc)
    despues = hechos(c, pid)
    assert [h["status"] for h in despues if h["category"] == "certificacion"] == ["rechazado"]
    educ = [h for h in despues if h["category"] == "educacion"]
    assert len(educ) == 1 and educ[0]["status"] == "editado"


def test_borrar_un_documento_conserva_lo_aprobado(con_hechos):
    _, c, pid, doc = con_hechos
    aprobado = uno(c, pid, "educacion")
    editado = uno(c, pid, "idioma")
    rechazado = uno(c, pid, "certificacion")
    accion(c, aprobado["id"], "confirmar")
    accion(c, editado["id"], "editar", {"idioma": "Inglés", "nivel": "B1"})
    accion(c, rechazado["id"], "rechazar")
    assert c.delete(f"/api/documentos/{doc}").status_code == 204
    quedan = hechos(c, pid)
    assert {h["id"] for h in quedan} == {aprobado["id"], editado["id"]}
    assert all(h["document_id"] is None and h["status"] in ("confirmado", "editado") for h in quedan)
    assert all(h["quote"] for h in quedan)  # la cita original sigue disponible


def test_la_revision_exige_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.patch("/api/hechos/x", json={"accion": "confirmar"}).status_code == 401
        assert c.post("/api/perfiles/x/hechos", json={"categoria": "idioma", "datos": {}}).status_code == 401
        assert (
            c.post("/api/perfiles/x/hechos/lote", json={"ids": ["a"], "accion": "confirmar"}).status_code
            == 401
        )
    app.state.engine.dispose()


# ------------------------------------------------------------------ migracion 0004
def test_migracion_0004_conserva_los_datos_y_permite_datos_propios(settings):
    settings.data_dir.mkdir(parents=True)
    command.upgrade(_alembic_config(settings), "0003")
    con = sqlite3.connect(settings.db_path)
    con.execute(
        "INSERT INTO profiles VALUES ('p1','Ana',NULL,NULL,NULL,NULL,NULL,'[]',NULL,'2026-01-01','2026-01-01')"
    )
    con.execute(
        "INSERT INTO documents VALUES ('d1','p1','cv.pdf','d1.pdf','pdf',10,'h','leido',1,'[]','t',NULL,'2026-01-01')"
    )
    con.execute(
        "INSERT INTO extracted_facts VALUES ('f1','p1','d1','educacion',?, 'cita',1,'[]',0,'confirmado','2026-01-01','2026-01-01')",
        (json.dumps({"titulo": "Ingeniería"}),),
    )
    con.commit()
    con.close()

    backup = migrate(settings)
    assert backup is not None  # la BD no estaba en head: se hizo copia
    con = sqlite3.connect(settings.db_path)
    con.execute("PRAGMA foreign_keys=ON")
    fila = con.execute(
        "SELECT id, document_id, origin, original_data, status, quote FROM extracted_facts"
    ).fetchone()
    assert fila == ("f1", "d1", "documento", None, "confirmado", "cita")
    # ahora admite datos sin documento y SET NULL al borrar el documento
    con.execute(
        "INSERT INTO extracted_facts VALUES ('f2','p1',NULL,'manual','idioma','{}',NULL,'',NULL,'[]',0,'confirmado','2026-01-01','2026-01-01')"
    )
    con.execute("DELETE FROM documents WHERE id='d1'")
    assert con.execute("SELECT document_id FROM extracted_facts WHERE id='f1'").fetchone() == (None,)
    idx = {r[1] for r in con.execute("PRAGMA index_list(extracted_facts)")}
    assert {"ix_extracted_facts_profile_id", "ix_extracted_facts_document_id"} <= idx
    con.close()


def test_documentos_y_perfil_siguen_funcionando_tras_migrar(settings):
    app, c = app_client(settings, FakeProvider([BUENA]))
    with c:
        pid = crear_perfil(c)
        r = subir(c, pid, df.make_pdf_text([df.CV_TEXTO]))
        assert esperar(c, r.json()["tarea"]["id"])["estado"] == "completado"
    app.state.engine.dispose()
