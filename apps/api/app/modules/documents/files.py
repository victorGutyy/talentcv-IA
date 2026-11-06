"""Validacion de archivos subidos: el tipo se decide por el contenido, nunca por la extension."""

import io
import re
import zipfile

PDF = b"%PDF-"
PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff"

EXTENSION = {"pdf": "pdf", "docx": "docx", "image": "img"}
MAX_UNZIPPED = 100 * 1024 * 1024  # proteccion contra "zip bombs" en DOCX


class InvalidFile(ValueError):
    """Archivo rechazado; el mensaje es apto para mostrar al usuario."""


def detect_kind(data: bytes) -> str:
    if PDF in data[:1024]:  # la especificacion permite basura antes de la cabecera
        return "pdf"
    if data.startswith(PNG) or data.startswith(JPEG):
        return "image"
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "[Content_Types].xml" in names and "word/document.xml" in names:
                    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
                        raise InvalidFile("El documento DOCX descomprimido es demasiado grande.")
                    return "docx"
        except zipfile.BadZipFile:
            pass
    raise InvalidFile("Formato no admitido. Sube un PDF, un DOCX o una imagen PNG o JPG.")


def image_extension(data: bytes) -> str:
    return "png" if data.startswith(PNG) else "jpg"


def safe_display_name(name: str) -> str:
    """Nombre solo para mostrar: sin rutas ni caracteres de control. Nunca se usa en disco."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "documento")[:255]
