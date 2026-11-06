import io

import docx
import pytest
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.ai.fake import FakeProvider
from app.modules.export.cv import CV, Puesto, sanear
from app.modules.export.plantillas import PLANTILLAS
from app.modules.export.router import nombre_archivo
from tests.test_writing import accion, agregar, borradores, cargar_datos, montar, redactar, respuestas  # noqa: F401


def informe(c, pid) -> dict:
    r = c.get(f"/api/perfiles/{pid}/curriculum")
    assert r.status_code == 200, r.text
    return r.json()


def exportar(c, pid, plantilla="ats", formato="docx", papel="carta"):
    return c.post(
        f"/api/perfiles/{pid}/exportar", json={"plantilla": plantilla, "formato": formato, "papel": papel}
    )


def abrir(resp) -> docx.document.Document:
    assert resp.status_code == 200, resp.text
    return docx.Document(io.BytesIO(resp.content))


def textos(d) -> list[str]:
    return [p.text for p in d.paragraphs]


@pytest.fixture
def cv_completo(montar):  # noqa: F811
    """Perfil con datos aprobados y textos redactados (aun sin aprobar)."""
    app, c, pid = montar(FakeProvider(respuestas()))
    c.put(
        f"/api/perfiles/{pid}",
        json={
            "nombre_completo": "Laura Méndez Ríos",
            "titular": "Desarrolladora de software",
            "email": "laura@example.com",
            "ciudad": "Bogotá",
            "pais": "Colombia",
            "enlaces": [{"etiqueta": "GitHub", "url": "https://github.com/laura"}],
        },
    )
    exp, lg = cargar_datos(c, pid)
    agregar(c, pid, "experiencia", cargo="Analista de datos", empresa="Horizonte", inicio="2018", fin="2020")
    agregar(
        c,
        pid,
        "educacion",
        titulo="Ingeniería Informática",
        institucion="Universidad del Norte",
        fecha_graduacion="2019",
    )
    agregar(c, pid, "idioma", idioma="Inglés", nivel="B2")
    agregar(c, pid, "certificacion", nombre="Scrum Fundamentals", emisor="Scrum.org", fecha="2021")
    redactar(c, pid)
    return app, c, pid, exp, lg


# ------------------------------------------------------------------ solo lo aprobado
def test_borradores_sin_aprobar_no_entran(cv_completo):
    _, c, pid, _, _ = cv_completo
    r = informe(c, pid)
    assert r["cv"]["resumen"] is None  # el resumen redactado sigue en borrador
    p = next(p for p in r["cv"]["experiencia"] if p["cargo"].startswith("Desarrolladora"))
    # sin texto aprobado, el punto es el logro ORIGINAL que el usuario aprobó, no el de la IA
    assert p["puntos"] == ["Reduje el tiempo de generación de reportes de 40 a 12 minutos"]
    assert any("sin aprobar" in a for a in r["advertencias"])
    assert any("resumen" in a for a in r["advertencias"])


def test_aprobar_el_borrador_lo_incluye(cv_completo):
    _, c, pid, _, _ = cv_completo
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    r = informe(c, pid)
    assert r["cv"]["resumen"].startswith("Desarrolladora de software con experiencia")
    p = next(p for p in r["cv"]["experiencia"] if p["cargo"].startswith("Desarrolladora"))
    assert p["puntos"] == ["Redujo el tiempo de reportes de 40 a 12 minutos."]  # texto redactado y aprobado
    assert not any("sin aprobar" in a for a in r["advertencias"])


def test_borrador_rechazado_vuelve_al_logro_original(cv_completo):
    _, c, pid, _, _ = cv_completo
    punto = next(d for d in borradores(c, pid) if d["seccion"] == "logro")
    accion(c, punto["id"], "rechazar")
    p = next(p for p in informe(c, pid)["cv"]["experiencia"] if p["cargo"].startswith("Desarrolladora"))
    assert p["puntos"] == ["Reduje el tiempo de generación de reportes de 40 a 12 minutos"]


def test_datos_pendientes_o_rechazados_no_entran(cv_completo):
    _, c, pid, _, _ = cv_completo
    hechos = c.get(f"/api/perfiles/{pid}/hechos").json()
    cert = next(h for h in hechos if h["category"] == "certificacion")
    idioma = next(h for h in hechos if h["category"] == "idioma")
    c.patch(f"/api/hechos/{cert['id']}", json={"accion": "restaurar"})  # vuelve a pendiente
    c.patch(f"/api/hechos/{idioma['id']}", json={"accion": "rechazar"})
    r = informe(c, pid)
    assert r["cv"]["certificaciones"] == [] and r["cv"]["idiomas"] == []
    assert any("pendientes" in a for a in r["advertencias"])


def test_resumen_del_perfil_como_alternativa(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    c.put(
        f"/api/perfiles/{pid}",
        json={"nombre_completo": "Ana Prueba", "resumen": "Texto que escribí yo misma."},
    )
    assert informe(c, pid)["cv"]["resumen"] == "Texto que escribí yo misma."


# ------------------------------------------------------------------ armado
def test_orden_cronologico_y_fechas(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    agregar(c, pid, "experiencia", cargo="Antiguo", inicio="2010", fin="2012")
    agregar(c, pid, "experiencia", cargo="Actual", inicio="marzo 2020", fin="actualidad")
    agregar(c, pid, "experiencia", cargo="Medio", inicio="2015", fin="2018")
    agregar(c, pid, "experiencia", cargo="Sin fechas")
    exp = informe(c, pid)["cv"]["experiencia"]
    assert [p["cargo"] for p in exp] == ["Actual", "Medio", "Antiguo", "Sin fechas"]
    assert exp[0]["fechas"] == "marzo 2020 – actualidad" and exp[3]["fechas"] is None


def test_contacto_perfil_manda_y_datos_aprobados_completan(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    c.put(f"/api/perfiles/{pid}", json={"nombre_completo": "Ana", "email": "ana@example.com"})
    agregar(c, pid, "contacto", tipo="email", valor="otro@example.com")
    agregar(c, pid, "contacto", tipo="telefono", valor="+57 300 000 0000")
    agregar(c, pid, "contacto", tipo="ciudad", valor="Cali")
    ct = informe(c, pid)["cv"]["contacto"]
    assert (
        ct["email"] == "ana@example.com"
        and ct["telefono"] == "+57 300 000 0000"
        and ct["ubicacion"] == "Cali"
    )


def test_habilidades_sin_duplicados_y_logros_sin_puesto(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    agregar(c, pid, "habilidad", nombres=["Python", "SQL"])
    agregar(c, pid, "habilidad", nombres=["python", "Docker"])
    agregar(c, pid, "logro", texto="Gané un concurso interno de innovación")
    cv = informe(c, pid)["cv"]
    assert cv["habilidades"] == ["Python", "SQL", "Docker"]
    assert cv["logros"] == ["Gané un concurso interno de innovación"]


def test_advertencias_de_un_perfil_vacio(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    a = informe(c, pid)["advertencias"]
    assert (
        any("experiencia" in x for x in a)
        and any("contacto" in x for x in a)
        and any("resumen" in x for x in a)
    )


def test_sanear_quita_caracteres_de_control():
    cv = CV(nombre="Ana\x00 Pérez", experiencia=[Puesto(cargo="Dev\x07", puntos=["Hizo\x0b algo"])])
    s = sanear(cv)
    assert (
        s.nombre == "Ana Pérez"
        and s.experiencia[0].cargo == "Dev"
        and s.experiencia[0].puntos == ["Hizo algo"]
    )


# ------------------------------------------------------------------ plantillas y DOCX
def test_lista_de_plantillas(client):
    r = client.get("/api/plantillas")
    assert [p["id"] for p in r.json()] == ["ats", "ejecutivo", "tecnologico"]
    ats = r.json()[0]
    assert ats["color"] is None and ats["secciones"][0] == "Resumen profesional"


@pytest.mark.parametrize("plantilla", list(PLANTILLAS))
@pytest.mark.parametrize("papel", ["carta", "a4"])
def test_docx_valido_para_cada_plantilla_y_papel(cv_completo, plantilla, papel):
    _, c, pid, _, _ = cv_completo
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    resp = exportar(c, pid, plantilla, "docx", papel)
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert resp.content[:2] == b"PK"
    d = abrir(resp)
    t = "\n".join(textos(d))
    for esperado in (
        "Laura Méndez Ríos",
        "Desarrolladora de software",
        "laura@example.com",
        "Bogotá, Colombia",
        "Tecnosur S.A.S.",
        "marzo 2020 – actualidad",
        "Universidad del Norte",
        "Python, FastAPI, SQL",
        "Inglés (B2)",
        "Scrum Fundamentals",
        "GitHub: https://github.com/laura",
    ):
        assert esperado in t, esperado
    assert d.tables == []  # ATS: sin tablas
    assert not d.inline_shapes  # ni imagenes
    ancho_cm = d.sections[0].page_width.cm
    assert round(ancho_cm, 1) == (21.6 if papel == "carta" else 21.0)
    assert (
        d.core_properties.title == "Currículum – Laura Méndez Ríos"
        and d.core_properties.author == "Laura Méndez Ríos"
    )


def test_docx_usa_titulos_y_vinetas_reales_de_word(cv_completo):
    _, c, pid, _, _ = cv_completo
    d = abrir(exportar(c, pid, "ats"))
    estilos = [p.style.name for p in d.paragraphs]
    assert estilos[0] == "Title"
    assert "Heading 1" in estilos and "Heading 2" in estilos and "List Bullet" in estilos
    h1 = [p.text for p in d.paragraphs if p.style.name == "Heading 1"]
    assert h1[:2] == ["Experiencia laboral", "Educación"]  # el resumen no esta aprobado: no hay seccion


def test_docx_solo_incluye_lo_aprobado(cv_completo):
    _, c, pid, _, _ = cv_completo
    t = "\n".join(textos(abrir(exportar(c, pid, "ats"))))
    assert "Desarrolladora de software con experiencia en Python y FastAPI." not in t  # resumen sin aprobar
    assert "Resumen profesional" not in t
    assert "Reduje el tiempo de generación de reportes de 40 a 12 minutos" in t  # logro original aprobado


def test_cada_plantilla_tiene_su_estilo(cv_completo):
    _, c, pid, _, _ = cv_completo
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    ats, ejec, tec = (abrir(exportar(c, pid, p)) for p in ("ats", "ejecutivo", "tecnologico"))
    assert ats.styles["Normal"].font.name == "Calibri" and ejec.styles["Normal"].font.name == "Georgia"
    assert (
        ejec.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.CENTER
        and ats.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.LEFT
    )
    # ATS sin color; ejecutivo con acento azul marino en los titulos
    assert ats.styles["Heading 1"].font.color.rgb == docx.shared.RGBColor(0, 0, 0)
    assert ejec.styles["Heading 1"].font.color.rgb == docx.shared.RGBColor(31, 56, 100)
    h1 = lambda d: [p.text for p in d.paragraphs if p.style.name == "Heading 1"]  # noqa: E731
    assert h1(tec).index("STACK TÉCNICO") < h1(tec).index("EXPERIENCIA")  # las habilidades van primero
    assert h1(ats).index("Experiencia laboral") < h1(ats).index("Habilidades")
    assert "Perfil ejecutivo" in h1(ejec) and "Trayectoria profesional" in h1(ejec)


def test_fechas_alineadas_con_tabulador_derecho(cv_completo):
    _, c, pid, _, _ = cv_completo
    d = abrir(exportar(c, pid, "ats"))
    p = next(p for p in d.paragraphs if "Tecnosur" in p.text and p.style.name == "Heading 2")
    assert "\tmarzo 2020 – actualidad" in p.text
    assert len(p.paragraph_format.tab_stops) == 1


def test_caracteres_especiales_y_de_control(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    c.put(f"/api/perfiles/{pid}", json={"nombre_completo": "Zoë Ñandú & <Co>"})
    agregar(c, pid, "experiencia", cargo="Dev \u0000 <b>x</b> & «ñ»", empresa="A&B")
    d = abrir(exportar(c, pid, "ats"))
    t = "\n".join(textos(d))
    assert (
        "Zoë Ñandú & <Co>" in t and "Dev  <b>x</b> & «ñ» — A&B" in t
    )  # se conserva el texto, sin el byte nulo


def test_documento_enorme_no_falla(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    for i in range(12):
        agregar(
            c,
            pid,
            "experiencia",
            cargo=f"Puesto {i}",
            empresa=f"Empresa {i}",
            inicio=str(2000 + i),
            fin=str(2001 + i),
        )
        for j in range(5):
            agregar(
                c,
                pid,
                "logro",
                texto=f"Logro {j} del puesto {i} con detalles " * 3,
                contexto=f"Puesto {i} – Empresa {i}",
            )
    d = abrir(exportar(c, pid, "tecnologico"))
    assert sum(1 for p in d.paragraphs if p.style.name == "List Bullet") == 60


# ------------------------------------------------------------------ API
def test_nombre_de_archivo_ascii():
    assert nombre_archivo("Laura Méndez Ríos", "ats", "docx") == "CV_Laura_Mendez_Rios_ats.docx"
    assert nombre_archivo('../../etc/passwd"; x', "ats", "pdf") == "CV_etc_passwd_x_ats.pdf"
    assert nombre_archivo("???", "ejecutivo", "docx") == "CV_Curriculum_ejecutivo.docx"


def test_cabeceras_de_descarga(cv_completo):
    _, c, pid, _, _ = cv_completo
    r = exportar(c, pid, "ejecutivo")
    assert r.headers["content-disposition"] == 'attachment; filename="CV_Laura_Mendez_Rios_ejecutivo.docx"'
    assert r.headers["cache-control"] == "no-store"


def test_errores_de_la_exportacion(cv_completo):
    _, c, pid, _, _ = cv_completo
    assert exportar(c, pid, "no-existe").status_code == 422
    assert (
        c.post(f"/api/perfiles/{pid}/exportar", json={"plantilla": "ats", "formato": "odt"}).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/perfiles/{pid}/exportar", json={"plantilla": "ats", "formato": "docx", "papel": "oficio"}
        ).status_code
        == 422
    )
    assert exportar(c, "noexiste").status_code == 404
    assert c.get("/api/perfiles/noexiste/curriculum").status_code == 404


def test_la_exportacion_exige_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/plantillas").status_code == 401
        assert c.get("/api/perfiles/x/curriculum").status_code == 401
        assert (
            c.post("/api/perfiles/x/exportar", json={"plantilla": "ats", "formato": "docx"}).status_code
            == 401
        )
    app.state.engine.dispose()
