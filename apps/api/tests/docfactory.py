"""Generadores de documentos FICTICIOS para pruebas (sin datos reales)."""

import io
import zipfile
from pathlib import Path

CV_TEXTO = """Laura Méndez Ríos
Desarrolladora de software
laura.mendez@example.com | +57 310 000 0000 | Bogotá, Colombia

EXPERIENCIA
Desarrolladora de software - Tecnosur S.A.S. (marzo 2020 - actualidad)
Redujo el tiempo de generación de reportes de 40 a 12 minutos.
Analista de datos - Comercial Horizonte (2018 - 2020)

EDUCACIÓN
Ingeniería Informática - Universidad del Norte

CERTIFICACIONES
Scrum Fundamentals Certified

IDIOMAS
Español (nativo), Inglés (intermedio)

HABILIDADES
Python, FastAPI, SQL, Power BI
"""
# Trampas: no hay fecha de graduacion ni emisor de la certificacion.


def make_pdf_text(pages: list[str]) -> bytes:
    """PDF valido con texto real (Helvetica, WinAnsi) escrito a mano."""
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, text in enumerate(pages):
        page_obj, content_obj = 4 + 2 * i, 5 + 2 * i
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_obj} 0 R "
                "/Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode()
        )
        stream = b"BT /F1 11 Tf 14 TL 40 800 Td "
        for line in text.split("\n"):
            esc = line.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            stream += b"(" + esc + b") Tj T* "
        stream += b"ET"
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        assert page_obj + 1 == content_obj

    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def make_docx(
    paragraphs: list[str], table_rows: list[list[str]] | None = None, header: str | None = None
) -> bytes:
    import docx

    d = docx.Document()
    if header:
        d.sections[0].header.paragraphs[0].text = header
    for p in paragraphs:
        d.add_paragraph(p)
    if table_rows:
        t = d.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r, row in enumerate(table_rows):
            for c, val in enumerate(row):
                t.cell(r, c).text = val
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _font(size: int):
    from PIL import ImageFont

    for candidate in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def make_image(text: str, fmt: str = "PNG", size: int = 38):
    from PIL import Image, ImageDraw

    lines = text.split("\n")
    font = _font(size)
    img = Image.new("RGB", (1500, 60 + int(size * 1.6) * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    y = 30
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += int(size * 1.6)
    return img


def make_image_bytes(text: str, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    make_image(text).save(buf, format=fmt)
    return buf.getvalue()


def make_scanned_pdf(text: str) -> bytes:
    """PDF que contiene solo una imagen (sin capa de texto), como un escaneo."""
    buf = io.BytesIO()
    make_image(text).save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def make_zip_bomb_docx() -> bytes:
    """DOCX 'valido' que se descomprime a >100 MB."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", b"\x00" * (101 * 1024 * 1024))
    return buf.getvalue()
