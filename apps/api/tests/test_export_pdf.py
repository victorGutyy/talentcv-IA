import io

import pytest
from pypdf import PdfReader

from app.ai.fake import FakeProvider
from app.modules.export.plantillas import PLANTILLAS
from tests.test_export import cv_completo, exportar  # noqa: F401
from tests.test_writing import accion, agregar, borradores, montar, respuestas  # noqa: F401


def leer(resp) -> PdfReader:
    assert resp.status_code == 200, resp.text
    return PdfReader(io.BytesIO(resp.content))


def texto(r: PdfReader) -> str:
    return "\n".join(p.extract_text() for p in r.pages)


def posiciones(r: PdfReader, pagina: int = 0) -> dict[str, float]:
    """x de inicio de cada fragmento de texto de la pagina."""
    out: dict[str, float] = {}

    def visitor(t, cm, tm, font_dict, font_size):
        if t.strip():
            out.setdefault(t.strip(), round(tm[4], 1))

    r.pages[pagina].extract_text(visitor_text=visitor)
    return out


@pytest.mark.parametrize("plantilla", list(PLANTILLAS))
@pytest.mark.parametrize("papel", ["carta", "a4"])
def test_pdf_valido_con_texto_seleccionable(cv_completo, plantilla, papel):
    _, c, pid, _, _ = cv_completo
    for d in borradores(c, pid):
        accion(c, d["id"], "aprobar")
    resp = exportar(c, pid, plantilla, "pdf", papel)
    assert resp.headers["content-type"] == "application/pdf" and resp.content[:5] == b"%PDF-"
    r = leer(resp)
    t = texto(r)
    for esperado in (
        "Laura Méndez Ríos",
        "Desarrolladora de software",
        "laura@example.com",
        "Bogotá, Colombia",
        "Tecnosur S.A.S.",
        "marzo 2020 – actualidad",
        "Ingeniería Informática",
        "Universidad del Norte",
        "Python, FastAPI, SQL",
        "Inglés (B2)",
        "Scrum Fundamentals",
        PLANTILLAS[plantilla].titulo("educacion"),
    ):
        assert esperado in t, esperado
    ancho, alto = (float(x) for x in r.pages[0].mediabox[2:])
    assert (round(ancho), round(alto)) == ((612, 792) if papel == "carta" else (595, 842))
    assert len(r.pages) == 1
    assert r.metadata.title == "Currículum – Laura Méndez Ríos" and r.metadata.author == "Laura Méndez Ríos"
    assert r.metadata.creator == "TalentCV AI"


def test_pdf_solo_incluye_lo_aprobado(cv_completo):
    _, c, pid, _, _ = cv_completo
    t = texto(leer(exportar(c, pid, "ats", "pdf")))
    assert "Resumen profesional" not in t  # el resumen sigue en borrador
    assert "Reduje el tiempo de generación de reportes de 40 a 12 minutos" in t  # logro original aprobado


def test_pdf_orden_de_secciones_por_plantilla(cv_completo):
    _, c, pid, _, _ = cv_completo
    tec = texto(leer(exportar(c, pid, "tecnologico", "pdf")))
    assert tec.index("STACK TÉCNICO") < tec.index("EXPERIENCIA") < tec.index("EDUCACIÓN")
    ats = texto(leer(exportar(c, pid, "ats", "pdf")))
    assert ats.index("Experiencia laboral") < ats.index("Habilidades")


def test_pdf_enlaces_clicables(cv_completo):
    _, c, pid, _, _ = cv_completo
    r = leer(exportar(c, pid, "ejecutivo", "pdf"))
    uris = [a.get_object()["/A"]["/URI"] for a in r.pages[0].get("/Annots", [])]
    assert "https://github.com/laura" in uris


def borde_derecho_del_texto(contenido: bytes) -> tuple[float, float]:
    """(x maximo ocupado por texto, ancho de pagina) en puntos, con las cajas de caracteres de pdfium."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(contenido)
    page = pdf[0]
    tp = page.get_textpage()
    maximo = max(tp.get_charbox(i)[2] for i in range(tp.count_chars()) if tp.get_text_range(i, 1).strip())
    ancho = page.get_width()
    pdf.close()
    return maximo, ancho


@pytest.mark.parametrize("plantilla", list(PLANTILLAS))
def test_pdf_las_fechas_no_se_salen_del_margen_derecho(cv_completo, plantilla):
    """Regresion: las tablas de cargo/fecha medían el ancho completo y las fechas invadían 6 pt del margen."""
    _, c, pid, _, _ = cv_completo
    maximo, ancho = borde_derecho_del_texto(exportar(c, pid, plantilla, "pdf").content)
    margen_pt = PLANTILLAS[plantilla].margen_cm / 2.54 * 72
    limite = ancho - margen_pt - 6  # el marco de reportlab deja 6 pt de relleno
    assert maximo <= limite + 0.6, f"{plantilla}: el texto llega a {maximo:.1f} y el limite es {limite:.1f}"
    assert maximo >= limite - 12, "las fechas deberian quedar pegadas al borde derecho"


def test_pdf_filas_alineadas_con_el_resto_del_texto(cv_completo):
    """El cargo y su fecha empiezan en el mismo margen izquierdo que los titulos."""
    _, c, pid, _, _ = cv_completo
    for plantilla in PLANTILLAS:
        pos = posiciones(leer(exportar(c, pid, plantilla, "pdf")))
        titulo = pos[PLANTILLAS[plantilla].titulo("experiencia")]
        cargo = next(v for k, v in pos.items() if k.startswith("Desarrolladora de software —"))
        assert abs(titulo - cargo) < 0.6, (plantilla, titulo, cargo)


def test_pdf_caracteres_especiales_no_rompen(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    c.put(
        f"/api/perfiles/{pid}",
        json={"nombre_completo": "Zoë Ñandú & <Co>", "titular": "Ingeniero 😀 de datos"},
    )
    agregar(
        c,
        pid,
        "experiencia",
        cargo="Dev \u0000 <b>x</b> & «ñ»",
        empresa="A&B",
        inicio="2020",
        fin="actualidad",
    )
    agregar(
        c,
        pid,
        "logro",
        texto="Mejoré 日本語 y cumplí con 100% de las metas",
        contexto="Dev <b>x</b> & «ñ» – A&B",
    )
    t = texto(leer(exportar(c, pid, "ats", "pdf")))
    assert "Zoë Ñandú & <Co>" in t
    assert "<b>x</b>" in t and "A&B" in t  # el marcado de reportlab no interpreta el texto del usuario
    assert "Ingeniero" in t and "de datos" in t  # el emoji se sustituye, no rompe


def test_pdf_documento_largo_ocupa_varias_paginas(montar):
    _, c, pid = montar(FakeProvider(respuestas()))
    for i in range(14):
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
                texto=f"Logro {j} del puesto {i} con bastante detalle " * 3,
                contexto=f"Puesto {i} – Empresa {i}",
            )
    r = leer(exportar(c, pid, "ejecutivo", "pdf"))
    assert len(r.pages) >= 2
    t = texto(r)
    assert all(f"Puesto {i}" in t for i in range(14)) and t.count("Logro ") >= 70
    # ninguna pagina empieza con un titulo de puesto "huerfano" sin sus viñetas visibles
    for pg in r.pages[1:]:
        assert pg.extract_text().strip()


def test_pdf_y_docx_tienen_el_mismo_contenido(cv_completo):
    _, c, pid, _, _ = cv_completo
    import docx

    d = docx.Document(io.BytesIO(exportar(c, pid, "ats", "docx").content))
    t_docx = " ".join(p.text for p in d.paragraphs).replace("\t", " ")
    t_pdf = " ".join(texto(leer(exportar(c, pid, "ats", "pdf"))).split())
    for palabra in ("Tecnosur", "Universidad", "Python", "Inglés", "GitHub", "Bogotá"):
        assert palabra in t_docx and palabra in t_pdf
