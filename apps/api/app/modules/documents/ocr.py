"""OCR con Tesseract, ejecutado como proceso local (sin red)."""

import asyncio
import os
import shutil
import sys
from pathlib import Path

from app.core.config import Settings, default_data_dir
from app.core.errors import UserFacingError

_WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
LANG = "spa"
TIMEOUT_SECONDS = 180


class OcrUnavailable(UserFacingError):
    """Tesseract o su idioma no estan disponibles."""


class OcrError(UserFacingError):
    pass


def bundled_dir() -> Path | None:
    """Tesseract que viaja con la aplicacion instalada (carpeta `tesseract` junto al ejecutable)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else None
    env = os.environ.get("TCV_TESSERACT_DIR")
    carpeta = Path(env) if env else (base / "tesseract" if base else None)
    return carpeta if carpeta and (carpeta / "tesseract.exe").exists() else None


def find_tesseract(settings: Settings) -> str | None:
    if settings.tesseract_cmd and Path(settings.tesseract_cmd).exists():
        return settings.tesseract_cmd
    propio = bundled_dir()
    if propio:  # el que trae la app tiene prioridad: es el que se probo con esta version
        return str(propio / "tesseract.exe")
    found = shutil.which("tesseract")
    if found:
        return found
    return str(_WINDOWS_DEFAULT) if _WINDOWS_DEFAULT.exists() else None


def _tessdata(settings: Settings) -> Path | None:
    """Carpeta con spa.traineddata: la de los datos de la app, la del usuario o TESSDATA_PREFIX."""
    appdata = os.environ.get("APPDATA")
    user_dir = Path(appdata) / "TalentCV" / "tessdata" if appdata else Path.home() / ".talentcv" / "tessdata"
    candidates = [settings.tessdata_dir, default_data_dir() / "tessdata", user_dir]
    if bundled_dir():
        candidates.insert(0, bundled_dir() / "tessdata")
    if os.environ.get("TESSDATA_PREFIX"):
        candidates.append(Path(os.environ["TESSDATA_PREFIX"]))
    for d in candidates:
        if (d / f"{LANG}.traineddata").exists():
            return d
    return None


def ocr_available(settings: Settings) -> bool:
    return find_tesseract(settings) is not None and _tessdata(settings) is not None


async def ocr_image(settings: Settings, image_bytes: bytes) -> str:
    """Devuelve el texto de una imagen (PNG/JPG). Se cancela matando el proceso."""
    exe = find_tesseract(settings)
    if exe is None:
        raise OcrUnavailable(
            "Tesseract OCR no está instalado, así que no se pueden leer documentos escaneados."
        )
    tessdata = _tessdata(settings)
    if tessdata is None:
        raise OcrUnavailable(
            f"Falta el idioma español para el OCR ({settings.tessdata_dir}\\{LANG}.traineddata)."
        )

    args = [exe, "stdin", "stdout", "-l", LANG, "--tessdata-dir", str(tessdata), "--psm", "3"]
    flags = 0x08000000 if sys.platform == "win32" else 0  # sin ventana de consola
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=flags,
        env={**os.environ, "OMP_THREAD_LIMIT": "4"},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(image_bytes), timeout=TIMEOUT_SECONDS)
    except (asyncio.CancelledError, TimeoutError) as e:
        proc.kill()
        await proc.wait()
        if isinstance(e, TimeoutError):
            raise OcrError("El OCR tardó demasiado en una página.") from e
        raise
    if proc.returncode != 0:
        raise OcrError(f"El OCR falló: {err.decode('utf-8', 'replace')[:200]}")
    return out.decode("utf-8", "replace")
