"""Generacion del archivo final (DOCX o PDF) a partir de un CV: compartida por la exportacion actual
y por la re-descarga de una version guardada."""

import re
import unicodedata

from app.modules.export.cv import CV
from app.modules.export.docx_render import render_docx
from app.modules.export.plantillas import PAPELES, PLANTILLAS

TIPOS = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


class ExportError(Exception):
    """Mensaje apto para el usuario; `status` es el codigo HTTP sugerido."""

    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status


def nombre_archivo(nombre: str, plantilla: str, formato: str, version: int | None = None) -> str:
    """Solo ASCII: sin acentos, espacios ni caracteres peligrosos."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_") or "Curriculum"
    sufijo = f"_v{version}" if version else ""
    return f"CV_{base[:60]}_{plantilla}{sufijo}.{formato}"


def generar(cv: CV, plantilla_id: str, formato: str, papel: str) -> bytes:
    plantilla = PLANTILLAS.get(plantilla_id)
    if plantilla is None:
        raise ExportError(422, "Plantilla desconocida.")
    if papel not in PAPELES:
        raise ExportError(422, "Tamaño de papel desconocido.")
    if formato == "docx":
        return render_docx(cv, plantilla, papel)
    if formato == "pdf":
        try:
            from app.modules.export.pdf_render import render_pdf
        except ImportError:
            raise ExportError(501, "La exportación a PDF no está disponible en esta instalación.") from None
        return render_pdf(cv, plantilla, papel)
    raise ExportError(422, "Formato desconocido.")
