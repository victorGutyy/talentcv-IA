"""Guardado de archivos desde la ventana de escritorio.

El WebView de Windows no ofrece un buen dialogo de descargas para archivos creados en memoria, asi que la
interfaz llama a `guardar_archivo` (expuesto con pywebview) y el usuario elige donde guardar. En el navegador
normal la interfaz sigue usando una descarga estandar.
"""

import base64
import binascii
import re
from collections.abc import Callable
from pathlib import Path

EXTENSIONES = {".docx", ".pdf", ".tcvbackup"}
MAX_BYTES = 60 * 1024 * 1024

# (directorio_inicial, nombre_sugerido, extension) -> ruta elegida o None si se cancela
Dialogo = Callable[[str, str, str], str | None]
# directorio_inicial -> carpeta elegida o None si se cancela
DialogoCarpeta = Callable[[str], str | None]


def nombre_seguro(nombre: str) -> str:
    """Solo el nombre de archivo, sin rutas ni caracteres de control; extension permitida."""
    base = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", Path(str(nombre).replace("\\", "/")).name).strip(" .")
    if Path(base).suffix.lower() not in EXTENSIONES:
        raise ValueError("Tipo de archivo no permitido.")
    return base[:120]


class Api:
    """Se expone a la interfaz como `window.pywebview.api`. Todo metodo publico es invocable desde JavaScript."""

    def __init__(
        self,
        dialogo: Dialogo | None = None,
        carpeta_inicial: Path | None = None,
        dialogo_carpeta: DialogoCarpeta | None = None,
    ):
        self._dialogo = dialogo
        self._dialogo_carpeta = dialogo_carpeta
        self._carpeta = carpeta_inicial or (Path.home() / "Documents")

    def _conectar(self, dialogo: Dialogo, dialogo_carpeta: DialogoCarpeta | None = None) -> None:
        self._dialogo = dialogo
        self._dialogo_carpeta = dialogo_carpeta

    def seleccionar_carpeta(self) -> dict:
        """Deja elegir una carpeta (p. ej. la de una USB con una actualizacion). Solo devuelve la ruta elegida."""
        if self._dialogo_carpeta is None:
            return {"ok": False, "error": "No hay una ventana para elegir la carpeta."}
        carpeta = self._carpeta if self._carpeta.exists() else Path.home()
        elegida = self._dialogo_carpeta(str(carpeta))
        if not elegida:
            return {"ok": False, "cancelado": True}
        if not Path(elegida).is_dir():
            return {"ok": False, "error": "Esa carpeta no existe o no se puede abrir."}
        return {"ok": True, "ruta": str(elegida)}

    def guardar_archivo(self, nombre: str, contenido_base64: str) -> dict:
        try:
            nombre = nombre_seguro(nombre)
            datos = base64.b64decode(contenido_base64, validate=True)
        except (ValueError, binascii.Error):
            return {"ok": False, "error": "Archivo no válido."}
        if not datos or len(datos) > MAX_BYTES:
            return {"ok": False, "error": "El archivo está vacío o es demasiado grande."}
        if self._dialogo is None:
            return {"ok": False, "error": "No hay una ventana para elegir dónde guardar."}
        carpeta = self._carpeta if self._carpeta.exists() else Path.home()
        elegida = self._dialogo(str(carpeta), nombre, Path(nombre).suffix.lower().lstrip("."))
        if not elegida:
            return {"ok": False, "cancelado": True}
        destino = Path(elegida)
        if destino.suffix.lower() not in EXTENSIONES:  # el usuario quito o cambio la extension
            destino = destino.with_name(destino.name + Path(nombre).suffix)
        try:
            destino.write_bytes(datos)
        except OSError as e:
            return {
                "ok": False,
                "error": f"No se pudo guardar el archivo: {e.strerror or 'error de escritura'}.",
            }
        self._carpeta = destino.parent  # la proxima vez, empezar donde guardo
        return {"ok": True, "ruta": str(destino)}
