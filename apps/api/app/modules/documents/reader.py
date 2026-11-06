"""Lectura de texto de PDF, DOCX e imagenes (con OCR cuando hace falta)."""

import asyncio
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.core.errors import UserFacingError
from app.modules.documents.ocr import ocr_image

MIN_TEXT_CHARS = 10  # una pagina de PDF con menos texto se considera escaneada (vacia de texto)
OCR_DPI = 300
MAX_IMAGE_PIXELS = 50_000_000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ProgressCallback = Callable[[float, str], None]


class DocumentError(UserFacingError):
    """Documento ilegible; el mensaje es apto para mostrar al usuario."""


@dataclass
class ReadResult:
    pages: list[str]
    ocr_pages: list[int] = field(default_factory=list)  # base 1


def clean_text(text: str) -> str:
    text = _CONTROL.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------------------------------------------------------------- PDF
def _pdf_text_pages(path: Path, max_pages: int) -> list[str]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise DocumentError(
                "El PDF está protegido con contraseña. Quita la protección y vuelve a subirlo."
            )
        n = len(reader.pages)
        if n > max_pages:
            raise DocumentError(f"El PDF tiene {n} páginas; el máximo es {max_pages}.")
        return [(p.extract_text() or "") for p in reader.pages]
    except DocumentError:
        raise
    except (PdfReadError, ValueError, KeyError, OSError) as e:
        raise DocumentError("No se pudo leer el PDF; puede estar dañado.") from e


def _render_page_png(path: Path, index: int) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        bitmap = pdf[index].render(scale=OCR_DPI / 72)
        image = bitmap.to_pil().convert("L")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


async def _read_pdf(settings: Settings, path: Path, progress: ProgressCallback) -> ReadResult:
    progress(0.05, "Leyendo el texto del PDF…")
    texts = await asyncio.to_thread(_pdf_text_pages, path, settings.max_pdf_pages)
    result = ReadResult(pages=list(texts))
    pendientes = [i for i, t in enumerate(texts) if len(t.strip()) < MIN_TEXT_CHARS]
    for n, i in enumerate(pendientes, start=1):
        progress(
            0.1 + 0.85 * (n - 1) / len(pendientes),
            f"Aplicando OCR a la página {i + 1} ({n} de {len(pendientes)})…",
        )
        png = await asyncio.to_thread(_render_page_png, path, i)
        result.pages[i] = await ocr_image(settings, png)
        result.ocr_pages.append(i + 1)
    return result


# ---------------------------------------------------------------- DOCX
def _docx_text(path: Path) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(str(path))
    except Exception as e:  # noqa: BLE001 - python-docx lanza varios tipos
        raise DocumentError("No se pudo leer el documento DOCX; puede estar dañado.") from e

    lines: list[str] = []
    for section in document.sections:  # encabezados: a menudo traen el contacto
        for p in section.header.paragraphs:
            if p.text.strip() and p.text.strip() not in lines:
                lines.append(p.text.strip())
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            lines.append(Paragraph(child, document).text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, document).rows:
                cells: list[str] = []
                for c in row.cells:
                    t = c.text.strip().replace("\n", " ")
                    if t and (not cells or cells[-1] != t):  # celdas combinadas se repiten
                        cells.append(t)
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


async def _read_docx(path: Path, progress: ProgressCallback) -> ReadResult:
    progress(0.1, "Leyendo el documento DOCX…")
    return ReadResult(pages=[await asyncio.to_thread(_docx_text, path)])


# ---------------------------------------------------------------- Imagen
def _prepare_image(path: Path) -> bytes:
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(path) as img:
            img.load()
            out = io.BytesIO()
            img.convert("L").save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as e:
        raise DocumentError("No se pudo abrir la imagen o es demasiado grande.") from e


async def _read_image(settings: Settings, path: Path, progress: ProgressCallback) -> ReadResult:
    progress(0.1, "Preparando la imagen…")
    png = await asyncio.to_thread(_prepare_image, path)
    progress(0.3, "Aplicando OCR a la imagen…")
    return ReadResult(pages=[await ocr_image(settings, png)], ocr_pages=[1])


# ---------------------------------------------------------------- API
async def read_document(settings: Settings, kind: str, path: Path, progress: ProgressCallback) -> ReadResult:
    if kind == "pdf":
        result = await _read_pdf(settings, path, progress)
    elif kind == "docx":
        result = await _read_docx(path, progress)
    elif kind == "image":
        result = await _read_image(settings, path, progress)
    else:
        raise DocumentError("Tipo de documento no admitido.")
    result.pages = [clean_text(p) for p in result.pages]
    if sum(len(p) for p in result.pages) > settings.max_text_chars:
        raise DocumentError("El documento tiene demasiado texto.")
    if not any(p.strip() for p in result.pages):
        raise DocumentError("No se encontró texto legible en el documento.")
    return result
