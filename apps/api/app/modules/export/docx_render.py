"""Exportacion a DOCX real (python-docx): estilos de Word, titulos como encabezados y vinetas nativas."""

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.modules.export.cv import CV
from app.modules.export.plantillas import PAPELES, Plantilla


def _fuente(style, nombre: str) -> None:
    style.font.name = nombre
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), nombre)
    # Los estilos por defecto de python-docx usan fuentes de tema: se quitan para que mande el nombre.
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]


def _borde_inferior(par, color_hex: str) -> None:
    ppr = par._p.get_or_add_pPr()
    borde = OxmlElement("w:pBdr")
    linea = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", color_hex)):
        linea.set(qn(k), v)
    borde.append(linea)
    ppr.append(borde)


def _sin_borde(style) -> None:
    ppr = style.element.get_or_add_pPr()
    for b in ppr.findall(qn("w:pBdr")):
        ppr.remove(b)


def _rgb(c: tuple[int, int, int] | None) -> RGBColor:
    return RGBColor(*c) if c else RGBColor(0, 0, 0)


def render_docx(cv: CV, p: Plantilla, papel: str = "carta") -> bytes:
    doc = Document()
    ancho, alto = PAPELES[papel]
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(ancho), Cm(alto)
    for lado in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, lado, Cm(p.margen_cm))
    ancho_texto = Cm(ancho - 2 * p.margen_cm)

    # --- estilos
    normal = doc.styles["Normal"]
    _fuente(normal, p.fuente_docx)
    normal.font.size = Pt(p.tam_base)
    normal.paragraph_format.space_after = Pt(2)
    normal.paragraph_format.space_before = Pt(0)

    titulo = doc.styles["Title"]
    _fuente(titulo, p.fuente_docx)
    titulo.font.size = Pt(p.tam_nombre)
    titulo.font.bold = True
    titulo.font.color.rgb = _rgb(p.color)
    titulo.paragraph_format.space_after = Pt(2)
    _sin_borde(titulo)

    h1 = doc.styles["Heading 1"]
    _fuente(h1, p.fuente_docx)
    h1.font.size = Pt(p.tam_base + 1.5)
    h1.font.bold = True
    h1.font.color.rgb = _rgb(p.color)
    h1.paragraph_format.space_before = Pt(10)
    h1.paragraph_format.space_after = Pt(3)
    h1.paragraph_format.keep_with_next = True

    h2 = doc.styles["Heading 2"]
    _fuente(h2, p.fuente_docx)
    h2.font.size = Pt(p.tam_base + 0.5)
    h2.font.bold = True
    h2.font.italic = False
    h2.font.color.rgb = RGBColor(0, 0, 0)
    h2.paragraph_format.space_before = Pt(6)
    h2.paragraph_format.space_after = Pt(1)
    h2.paragraph_format.keep_with_next = True

    vineta = doc.styles["List Bullet"]
    _fuente(vineta, p.fuente_docx)
    vineta.font.size = Pt(p.tam_base)
    vineta.paragraph_format.space_after = Pt(1)

    acento_hex = "%02X%02X%02X" % (p.color or (0, 0, 0))

    # --- cabecera
    alinear = WD_ALIGN_PARAGRAPH.CENTER if p.cabecera_centrada else WD_ALIGN_PARAGRAPH.LEFT
    par = doc.add_paragraph(cv.nombre, style="Title")
    par.alignment = alinear
    if cv.titular:
        par = doc.add_paragraph()
        par.alignment = alinear
        r = par.add_run(cv.titular)
        r.font.size = Pt(p.tam_base + 2)
        r.font.color.rgb = _rgb(p.color)
    contacto = [x for x in (cv.contacto.email, cv.contacto.telefono, cv.contacto.ubicacion) if x]
    if contacto:
        par = doc.add_paragraph("  |  ".join(contacto))
        par.alignment = alinear
    for enlace in cv.contacto.enlaces:
        par = doc.add_paragraph(enlace)
        par.alignment = alinear

    # --- secciones
    def encabezado(seccion: str) -> None:
        par = doc.add_paragraph(p.titulo(seccion), style="Heading 1")
        if p.linea_bajo_titulos:
            _borde_inferior(par, acento_hex)

    def con_fecha(izq: str, der: str | None) -> None:
        par = doc.add_paragraph(style="Heading 2")
        par.paragraph_format.tab_stops.add_tab_stop(ancho_texto, WD_TAB_ALIGNMENT.RIGHT)
        par.add_run(izq)
        if der:
            r = par.add_run("\t" + der)
            r.font.bold = False
            r.font.size = Pt(p.tam_base)

    for seccion in p.orden:
        if seccion == "resumen" and cv.resumen:
            encabezado(seccion)
            doc.add_paragraph(cv.resumen)
        elif seccion == "experiencia" and cv.experiencia:
            encabezado(seccion)
            for puesto in cv.experiencia:
                con_fecha(
                    f"{puesto.cargo} — {puesto.empresa}" if puesto.empresa else puesto.cargo, puesto.fechas
                )
                for punto in puesto.puntos:
                    doc.add_paragraph(punto, style="List Bullet")
        elif seccion == "educacion" and cv.educacion:
            encabezado(seccion)
            for e in cv.educacion:
                con_fecha(f"{e.titulo} — {e.institucion}" if e.institucion else e.titulo, e.fecha)
        elif seccion == "habilidades" and cv.habilidades:
            encabezado(seccion)
            if p.habilidades_en_linea:
                doc.add_paragraph(", ".join(cv.habilidades))
            else:
                for h in cv.habilidades:
                    doc.add_paragraph(h, style="List Bullet")
        elif seccion == "certificaciones" and cv.certificaciones:
            encabezado(seccion)
            for c in cv.certificaciones:
                con_fecha(f"{c.nombre} — {c.emisor}" if c.emisor else c.nombre, c.fecha)
        elif seccion == "idiomas" and cv.idiomas:
            encabezado(seccion)
            doc.add_paragraph(", ".join(cv.idiomas))
        elif seccion == "logros" and cv.logros:
            encabezado(seccion)
            for lg in cv.logros:
                doc.add_paragraph(lg, style="List Bullet")

    # --- metadatos (los lee Word y algunos ATS)
    cp = doc.core_properties
    cp.title = f"Currículum – {cv.nombre}"
    cp.author = cv.nombre
    cp.subject = "Currículum vitae"
    cp.keywords = ""
    cp.comments = ""
    cp.last_modified_by = cv.nombre

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
