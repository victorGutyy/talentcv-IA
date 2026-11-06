"""Exportacion a PDF real (reportlab): texto seleccionable y buscable, una columna, fuentes estandar de PDF.

Las fuentes estandar (Helvetica, Times) usan la codificacion cp1252: cubren espanol e ingles. Un caracter
fuera de ese conjunto (p. ej. emojis) se reemplaza por su equivalente ASCII o por «?» en vez de salir roto.
"""

import io
import re
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.export.cv import CV
from app.modules.export.plantillas import PAPELES, Plantilla

FAMILIAS = {"Helvetica": ("Helvetica", "Helvetica-Bold"), "Times": ("Times-Roman", "Times-Bold")}
_URL = re.compile(r"(https?://[^\s<>\"]+)")


def _cp1252(texto: str) -> str:
    out = []
    for ch in texto:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
            out.append(base or "?")
    return "".join(out)


def _x(texto: str) -> str:
    """Texto seguro para el marcado de Paragraph: compatible con la fuente y con los & < > escapados."""
    return escape(_cp1252(texto))


def _con_enlaces(texto: str, color: str) -> str:
    """Escapa el texto y vuelve clicables las URL."""
    partes = _URL.split(_cp1252(texto))
    out = []
    for i, parte in enumerate(partes):
        if i % 2 == 1:
            url = escape(parte.rstrip(".,;)"), {'"': "&quot;"})
            resto = escape(parte[len(parte.rstrip(".,;)")) :])
            out.append(f'<a href="{url}" color="{color}">{url}</a>{resto}')
        else:
            out.append(escape(parte))
    return "".join(out)


def render_pdf(cv: CV, p: Plantilla, papel: str = "carta") -> bytes:
    normal, negrita = FAMILIAS[p.fuente_pdf]
    acento = colors.Color(*(c / 255 for c in p.color)) if p.color else colors.black
    acento_hex = "#%02x%02x%02x" % (p.color or (0, 0, 0))  # noqa: UP031
    ancho, alto = PAPELES[papel]
    margen = p.margen_cm * cm
    # El marco de SimpleDocTemplate deja 6 pt de relleno a cada lado: las tablas deben medir lo mismo que
    # el area util de los parrafos, o se salen y se centran (quedarian desalineadas con el resto).
    ancho_texto = (ancho - 2 * p.margen_cm) * cm - 12
    alinear = TA_CENTER if p.cabecera_centrada else TA_LEFT
    b = p.tam_base
    lead = b * 1.28

    def estilo(nombre: str, **kw) -> ParagraphStyle:
        base = {
            "fontName": normal,
            "fontSize": b,
            "leading": lead,
            "spaceAfter": 2,
            "textColor": colors.black,
        }
        return ParagraphStyle(nombre, **{**base, **kw})

    st_nombre = estilo(
        "nombre",
        fontName=negrita,
        fontSize=p.tam_nombre,
        leading=p.tam_nombre * 1.15,
        textColor=acento,
        alignment=alinear,
    )
    st_titular = estilo(
        "titular", fontSize=b + 2, leading=(b + 2) * 1.25, textColor=acento, alignment=alinear
    )
    st_cont = estilo("contacto", alignment=alinear)
    st_h1 = estilo(
        "h1",
        fontName=negrita,
        fontSize=b + 1.5,
        leading=(b + 1.5) * 1.25,
        textColor=acento,
        spaceBefore=10,
        spaceAfter=3,
        keepWithNext=1,
    )
    st_h2 = estilo("h2", fontName=negrita, fontSize=b + 0.5, spaceAfter=1)
    st_fecha = estilo("fecha", alignment=TA_RIGHT, spaceAfter=1)
    st_texto = estilo("texto")
    st_vineta = estilo("vineta", leftIndent=14, bulletIndent=4, spaceAfter=1)

    story: list = []

    def parrafo(texto: str, st: ParagraphStyle, **kw) -> Paragraph:
        return Paragraph(_con_enlaces(texto, acento_hex), st, **kw)

    def encabezado(seccion: str) -> list:
        h = Paragraph(_x(p.titulo(seccion)), st_h1)
        if not p.linea_bajo_titulos:
            return [h]
        return [h, HRFlowable(width="100%", thickness=0.7, color=acento, spaceBefore=0, spaceAfter=3)]

    def fila(izq: str, der: str | None) -> Table:
        t = Table(
            [[Paragraph(_x(izq), st_h2), Paragraph(_x(der or ""), st_fecha)]],
            colWidths=[ancho_texto * 0.72, ancho_texto * 0.28],
            hAlign="LEFT",
        )
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return t

    def vineta(texto: str) -> Paragraph:
        return Paragraph(_x(texto), st_vineta, bulletText="•")

    # --- cabecera
    story.append(Paragraph(_x(cv.nombre), st_nombre))
    if cv.titular:
        story.append(Paragraph(_x(cv.titular), st_titular))
    contacto = [x for x in (cv.contacto.email, cv.contacto.telefono, cv.contacto.ubicacion) if x]
    if contacto:
        story.append(Paragraph(_x("  |  ".join(contacto)), st_cont))
    for enlace in cv.contacto.enlaces:
        story.append(parrafo(enlace, st_cont))

    # --- secciones
    for seccion in p.orden:
        if seccion == "resumen" and cv.resumen:
            story += [KeepTogether([*encabezado(seccion), Paragraph(_x(cv.resumen), st_texto)])]
        elif seccion == "experiencia" and cv.experiencia:
            story += encabezado(seccion)
            for puesto in cv.experiencia:
                cab = fila(
                    f"{puesto.cargo} — {puesto.empresa}" if puesto.empresa else puesto.cargo, puesto.fechas
                )
                puntos = [vineta(x) for x in puesto.puntos]
                story.append(
                    KeepTogether([cab, *puntos[:1]])
                )  # el titulo del puesto no queda solo al final de la pagina
                story += puntos[1:]
                story.append(Spacer(1, 3))
        elif seccion == "educacion" and cv.educacion:
            story += encabezado(seccion)
            story += [
                fila(f"{e.titulo} — {e.institucion}" if e.institucion else e.titulo, e.fecha)
                for e in cv.educacion
            ]
        elif seccion == "habilidades" and cv.habilidades:
            story += [
                KeepTogether([*encabezado(seccion), Paragraph(_x(", ".join(cv.habilidades)), st_texto)])
            ]
        elif seccion == "certificaciones" and cv.certificaciones:
            story += encabezado(seccion)
            story += [
                fila(f"{c.nombre} — {c.emisor}" if c.emisor else c.nombre, c.fecha)
                for c in cv.certificaciones
            ]
        elif seccion == "idiomas" and cv.idiomas:
            story += [KeepTogether([*encabezado(seccion), Paragraph(_x(", ".join(cv.idiomas)), st_texto)])]
        elif seccion == "logros" and cv.logros:
            story += encabezado(seccion)
            story += [vineta(x) for x in cv.logros]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(ancho * cm, alto * cm),
        leftMargin=margen,
        rightMargin=margen,
        topMargin=margen,
        bottomMargin=margen,
        title=_cp1252(f"Currículum – {cv.nombre}"),
        author=_cp1252(cv.nombre),
        subject="Currículum vitae",
        creator="TalentCV AI",
    )
    doc.build(story)
    return buf.getvalue()
