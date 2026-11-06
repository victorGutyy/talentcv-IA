import io

import docx
from sqlalchemy.orm import sessionmaker

from app.ai.fake import FakeProvider
from app.modules.export.cv import CV, Estudio, Puesto
from app.modules.versions.diff import comparar
from app.modules.versions.models import CVVersion
from tests.test_export import cv_completo, exportar  # noqa: F401
from tests.test_writing import accion, agregar, borradores, montar, respuestas  # noqa: F401


def versiones(c, pid) -> list[dict]:
    r = c.get(f"/api/perfiles/{pid}/versiones")
    assert r.status_code == 200, r.text
    return r.json()


def guardar(c, pid, etiqueta=None):
    return c.post(f"/api/perfiles/{pid}/versiones", json={"etiqueta": etiqueta})


def textos(resp) -> str:
    assert resp.status_code == 200, resp.text
    return "\n".join(p.text for p in docx.Document(io.BytesIO(resp.content)).paragraphs)


# ------------------------------------------------------------------ versiones por exportacion
def test_exportar_crea_la_version_1_con_cabeceras(cv_completo):
    _, c, pid, _, _ = cv_completo
    r = exportar(c, pid, "ats")
    assert r.headers["x-version-number"] == "1" and len(r.headers["x-version-id"]) == 32
    vs = versiones(c, pid)
    assert [v["numero"] for v in vs] == [1] and vs[0]["origen"] == "exportacion"
    assert [(e["plantilla"], e["formato"]) for e in vs[0]["exportaciones"]] == [("ats", "docx")]


def test_mismo_contenido_no_duplica_versiones_solo_anota_la_exportacion(cv_completo):
    _, c, pid, _, _ = cv_completo
    exportar(c, pid, "ats", "docx")
    exportar(c, pid, "ejecutivo", "pdf", "a4")
    r = exportar(c, pid, "tecnologico", "docx")
    assert r.headers["x-version-number"] == "1"
    vs = versiones(c, pid)
    assert len(vs) == 1
    assert [e["plantilla"] for e in vs[0]["exportaciones"]] == ["ats", "ejecutivo", "tecnologico"]
    assert vs[0]["exportaciones"][1]["papel"] == "a4"


def test_cambiar_los_datos_crea_una_version_nueva(cv_completo):
    _, c, pid, _, _ = cv_completo
    exportar(c, pid, "ats")
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")  # el resumen y los puntos aprobados cambian el contenido
    r = exportar(c, pid, "ats")
    assert r.headers["x-version-number"] == "2"
    assert [v["numero"] for v in versiones(c, pid)] == [2, 1]  # la mas reciente primero
    assert versiones(c, pid)[0]["contenido"]["tiene_resumen"] is True
    assert versiones(c, pid)[1]["contenido"]["tiene_resumen"] is False


def test_lo_que_no_entra_al_cv_no_cambia_el_historial(cv_completo):
    """Datos rechazados o sin aprobar no alteran el contenido: no generan una version distinta."""
    _, c, pid, _, _ = cv_completo
    assert exportar(c, pid, "ats").headers["x-version-number"] == "1"
    francés = agregar(c, pid, "idioma", idioma="Francés", nivel="A2")
    c.patch(f"/api/hechos/{francés['id']}", json={"accion": "rechazar"})  # nunca llegó a exportarse
    assert exportar(c, pid, "ats").headers["x-version-number"] == "1"
    c.patch(f"/api/hechos/{francés['id']}", json={"accion": "restaurar"})  # pendiente: tampoco entra
    assert exportar(c, pid, "ats").headers["x-version-number"] == "1"
    c.patch(f"/api/hechos/{francés['id']}", json={"accion": "confirmar"})  # ahora sí entra
    assert exportar(c, pid, "ats").headers["x-version-number"] == "2"


# ------------------------------------------------------------------ guardar a mano
def test_guardar_a_mano_y_no_duplicar(cv_completo):
    _, c, pid, _, _ = cv_completo
    r = guardar(c, pid, "Para la entrevista de Tecnosur")
    assert r.status_code == 201 and r.json()["creada"] is True
    v = r.json()["version"]
    assert v["numero"] == 1 and v["origen"] == "manual" and v["etiqueta"] == "Para la entrevista de Tecnosur"
    r2 = guardar(c, pid, "Otro nombre")
    assert r2.status_code == 200 and r2.json()["creada"] is False
    assert (
        r2.json()["version"]["id"] == v["id"]
        and r2.json()["version"]["etiqueta"] == "Para la entrevista de Tecnosur"
    )


def test_guardar_pone_etiqueta_a_una_version_que_no_la_tenia(cv_completo):
    _, c, pid, _, _ = cv_completo
    exportar(c, pid, "ats")
    r = guardar(c, pid, "Etiqueta tardía")
    assert r.status_code == 200 and r.json()["version"]["etiqueta"] == "Etiqueta tardía"


def test_validacion_de_la_etiqueta(cv_completo):
    _, c, pid, _, _ = cv_completo
    assert guardar(c, pid, "x" * 81).status_code == 422
    assert guardar(c, pid, "   ").json()["version"]["etiqueta"] is None
    assert guardar(c, "noexiste").status_code == 404


# ------------------------------------------------------------------ ver, renombrar, borrar
def test_ver_renombrar_y_borrar(cv_completo):
    _, c, pid, _, _ = cv_completo
    v = guardar(c, pid).json()["version"]
    det = c.get(f"/api/versiones/{v['id']}").json()
    assert det["cv"]["nombre"] == "Laura Méndez Ríos" and det["cv"]["experiencia"][0]["cargo"]
    assert c.patch(f"/api/versiones/{v['id']}", json={"etiqueta": "Final"}).json()["etiqueta"] == "Final"
    assert c.patch(f"/api/versiones/{v['id']}", json={"etiqueta": ""}).json()["etiqueta"] is None
    assert c.delete(f"/api/versiones/{v['id']}").status_code == 204
    assert c.get(f"/api/versiones/{v['id']}").status_code == 404
    assert versiones(c, pid) == []
    assert c.delete(f"/api/versiones/{v['id']}").status_code == 404


def test_borrar_el_perfil_borra_su_historial(cv_completo):
    app, c, pid, _, _ = cv_completo
    exportar(c, pid, "ats")
    assert c.delete(f"/api/perfiles/{pid}").status_code == 204
    with sessionmaker(bind=app.state.engine)() as db:
        assert db.query(CVVersion).count() == 0


def test_una_version_guardada_por_una_app_anterior_sigue_abriendo(cv_completo):
    """Si el modelo del CV crece, las versiones viejas (sin los campos nuevos) se leen con valores por defecto."""
    app, c, pid, _, _ = cv_completo
    with sessionmaker(bind=app.state.engine)() as db:
        db.add(
            CVVersion(
                profile_id=pid,
                numero=7,
                origen="manual",
                content_hash="a" * 64,
                cv={"nombre": "Antigua", "experiencia": [{"cargo": "Dev"}]},
                exportaciones=[],
            )
        )
        db.commit()
    v = next(v for v in versiones(c, pid) if v["numero"] == 7)
    det = c.get(f"/api/versiones/{v['id']}").json()
    assert (
        det["cv"]["nombre"] == "Antigua"
        and det["cv"]["habilidades"] == []
        and det["cv"]["experiencia"][0]["puntos"] == []
    )
    assert (
        c.post(f"/api/versiones/{v['id']}/exportar", json={"plantilla": "ats", "formato": "docx"}).status_code
        == 200
    )


# ------------------------------------------------------------------ comparar
def test_comparar_con_el_estado_actual(cv_completo):
    _, c, pid, _, _ = cv_completo
    v = guardar(c, pid).json()["version"]
    igual = c.get(f"/api/versiones/{v['id']}/comparar").json()
    assert igual["iguales"] is True and igual["cambios"] == [] and igual["despues"] == "Estado actual"
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    r = c.get(f"/api/versiones/{v['id']}/comparar").json()
    assert r["antes"] == "Versión 1" and not r["iguales"]
    tipos = {(x["seccion"], x["tipo"]) for x in r["cambios"]}
    assert ("Resumen", "agregado") in tipos and (
        "Experiencia",
        "cambiado",
    ) in tipos  # el punto redactado reemplaza al original


def test_comparar_dos_versiones(cv_completo):
    _, c, pid, _, _ = cv_completo
    v1 = guardar(c, pid).json()["version"]
    agregar(c, pid, "habilidad", nombres=["Docker"])
    v2 = guardar(c, pid).json()["version"]
    r = c.get(f"/api/versiones/{v1['id']}/comparar", params={"con": v2["id"]}).json()
    assert r["despues"] == "Versión 2"
    assert {"seccion": "Habilidades", "tipo": "agregado", "antes": None, "despues": "Docker"} in r["cambios"]
    inversa = c.get(f"/api/versiones/{v2['id']}/comparar", params={"con": v1["id"]}).json()
    assert any(x["tipo"] == "quitado" and x["antes"] == "Docker" for x in inversa["cambios"])


def test_comparar_errores(cv_completo, montar):
    _, c, pid, _, _ = cv_completo
    v = guardar(c, pid).json()["version"]
    assert c.get(f"/api/versiones/{v['id']}/comparar", params={"con": "noexiste"}).status_code == 404
    assert c.get("/api/versiones/noexiste/comparar").status_code == 404
    otro = c.post("/api/perfiles", json={"nombre_completo": "Otra Persona"}).json()["id"]
    vo = guardar(c, otro).json()["version"]
    assert c.get(f"/api/versiones/{v['id']}/comparar", params={"con": vo["id"]}).status_code == 422


def test_diff_en_detalle():
    a = CV(
        nombre="Ana",
        titular="Dev",
        resumen="Hola",
        habilidades=["Python", "SQL"],
        experiencia=[Puesto(cargo="Dev", empresa="X", fechas="2020 – 2021", puntos=["Hizo A", "Hizo B"])],
        educacion=[Estudio(titulo="Ing", institucion="U")],
    )
    b = CV(
        nombre="Ana",
        titular="Dev Senior",
        resumen="Hola",
        habilidades=["Python", "Docker", "SQL"],
        experiencia=[
            Puesto(
                cargo="Dev", empresa="X", fechas="2020 – 2021", puntos=["Hizo A", "Hizo B mejorado", "Hizo C"]
            )
        ],
        educacion=[],
    )
    cambios = {(x.seccion, x.tipo, x.antes, x.despues) for x in comparar(a, b)}
    assert ("Cabecera", "cambiado", "Dev", "Dev Senior") in cambios
    assert ("Habilidades", "agregado", None, "Docker") in cambios
    assert ("Experiencia", "cambiado", "• Hizo B", "• Hizo B mejorado") in cambios
    assert ("Experiencia", "agregado", None, "• Hizo C") in cambios
    assert ("Educación", "quitado", "Ing — U", None) in cambios
    assert not any(x.seccion == "Resumen" for x in comparar(a, b))
    assert comparar(a, a) == []


# ------------------------------------------------------------------ recuperar el archivo de una version
def test_reexportar_entrega_el_contenido_de_esa_version_aunque_los_datos_cambien(cv_completo):
    _, c, pid, _, _ = cv_completo
    v1 = guardar(c, pid, "Antes").json()["version"]
    agregar(c, pid, "habilidad", nombres=["Docker"])  # los datos actuales ya no son los de v1
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    actual = textos(exportar(c, pid, "ats"))
    r = c.post(f"/api/versiones/{v1['id']}/exportar", json={"plantilla": "ats", "formato": "docx"})
    antiguo = textos(r)
    assert "Docker" in actual and "Docker" not in antiguo
    assert "Resumen profesional" in actual and "Resumen profesional" not in antiguo
    assert r.headers["content-disposition"] == 'attachment; filename="CV_Laura_Mendez_Rios_ats_v1.docx"'
    assert r.headers["x-version-number"] == "1"


def test_reexportar_en_otra_plantilla_y_formato_sin_crear_versiones(cv_completo):
    _, c, pid, _, _ = cv_completo
    v = guardar(c, pid).json()["version"]
    n = len(versiones(c, pid))
    r = c.post(
        f"/api/versiones/{v['id']}/exportar", json={"plantilla": "ejecutivo", "formato": "pdf", "papel": "a4"}
    )
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert len(versiones(c, pid)) == n
    assert [e["plantilla"] for e in versiones(c, pid)[0]["exportaciones"]] == ["ejecutivo"]


def test_reexportar_errores(cv_completo):
    _, c, pid, _, _ = cv_completo
    v = guardar(c, pid).json()["version"]
    assert (
        c.post(
            f"/api/versiones/{v['id']}/exportar", json={"plantilla": "nada", "formato": "docx"}
        ).status_code
        == 422
    )
    assert (
        c.post(f"/api/versiones/{v['id']}/exportar", json={"plantilla": "ats", "formato": "odt"}).status_code
        == 422
    )
    assert (
        c.post("/api/versiones/noexiste/exportar", json={"plantilla": "ats", "formato": "docx"}).status_code
        == 404
    )


def test_muchas_versiones(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    for i in range(30):
        agregar(c, pid, "habilidad", nombres=[f"Habilidad {i}"])
        assert guardar(c, pid).json()["creada"] is True
    vs = versiones(c, pid)
    assert len(vs) == 30 and [v["numero"] for v in vs] == list(range(30, 0, -1))


def test_el_historial_exige_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/perfiles/x/versiones").status_code == 401
        assert c.post("/api/perfiles/x/versiones", json={}).status_code == 401
        assert c.get("/api/versiones/x").status_code == 401
        assert c.get("/api/versiones/x/comparar").status_code == 401
        assert (
            c.post("/api/versiones/x/exportar", json={"plantilla": "ats", "formato": "docx"}).status_code
            == 401
        )
        assert c.delete("/api/versiones/x").status_code == 401
    app.state.engine.dispose()
