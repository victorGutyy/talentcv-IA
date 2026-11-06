"""Actualizaciones fuera de linea (USB): un paquete firmado con Ed25519 que la app verifica antes de ejecutarlo.

Un paquete es una carpeta con dos archivos:
  actualizacion.json                    {"manifiesto": {...}, "firma": "<base64>"}
  TalentCV-Setup-<version>.exe          el instalador

La firma cubre el manifiesto, y el manifiesto fija la version, el nombre, el tamano y el SHA-256 del instalador.
Asi, ni el instalador ni el manifiesto pueden alterarse, y un paquete firmado antiguo no sirve para bajar de version.
La CLAVE PRIVADA no esta en el repositorio ni en la app: solo la clave publica (`clave_publica.py`).
"""

import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nacl.exceptions import BadSignatureError, CryptoError
from nacl.signing import VerifyKey
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.system.clave_publica import CLAVE_PUBLICA

NOMBRE_MANIFIESTO = "actualizacion.json"
MAX_MANIFIESTO = 64 * 1024
MAX_INSTALADOR = 1024 * 1024 * 1024
_VERSION = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")
_INSTALADOR = re.compile(r"^TalentCV-Setup-(\d{1,3}\.\d{1,3}\.\d{1,3})\.exe$")


class Manifiesto(BaseModel):
    version: str
    archivo: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tamano: int = Field(gt=0, le=MAX_INSTALADOR)
    fecha: str = Field(max_length=40)
    notas: str = Field(default="", max_length=2000)

    @field_validator("version")
    @classmethod
    def _version(cls, v: str) -> str:
        if not _VERSION.match(v):
            raise ValueError("version no valida")
        return v

    @field_validator("archivo")
    @classmethod
    def _archivo(cls, v: str) -> str:
        if not _INSTALADOR.match(v):  # nada de rutas, subcarpetas ni otros ejecutables
            raise ValueError("nombre de instalador no valido")
        return v


@dataclass
class Resultado:
    ok: bool
    motivo: str  # ok | sin_paquete | formato | firma | no_es_nueva | archivo | hash
    mensaje: str
    manifiesto: Manifiesto | None = None
    instalador: Path | None = None


def tupla(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


def bytes_firmados(manifiesto: dict) -> bytes:
    """Representacion canonica: la misma para firmar y para verificar."""
    return json.dumps(manifiesto, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def verificar(carpeta: str | Path, version_actual: str, clave_publica: str | None = None) -> Resultado:
    """Comprueba un paquete de actualizacion. Nunca ejecuta nada."""
    clave_publica = clave_publica or CLAVE_PUBLICA  # se lee aqui (no al definir la funcion) para poder probar con otras claves
    carpeta = Path(carpeta)
    ruta_manifiesto = carpeta / NOMBRE_MANIFIESTO
    try:
        if not ruta_manifiesto.is_file():
            return Resultado(False, "sin_paquete", f"No hay un paquete de actualización en esa carpeta (falta {NOMBRE_MANIFIESTO}).")
        if ruta_manifiesto.stat().st_size > MAX_MANIFIESTO:
            return Resultado(False, "formato", "El archivo de la actualización no es válido.")
        crudo = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
        datos_manifiesto, firma_b64 = crudo["manifiesto"], crudo["firma"]
        manifiesto = Manifiesto.model_validate(datos_manifiesto)
        firma = base64.b64decode(firma_b64, validate=True)
    except (OSError, ValueError, KeyError, TypeError, ValidationError, binascii.Error):
        return Resultado(False, "formato", "El archivo de la actualización no es válido.")

    # 1) autenticidad: la firma debe ser de la clave publica incluida en esta app
    try:
        VerifyKey(base64.b64decode(clave_publica)).verify(bytes_firmados(manifiesto.model_dump()), firma)
    except (BadSignatureError, CryptoError, ValueError, binascii.Error):
        return Resultado(False, "firma", "La firma de la actualización no es válida: no se instalará.")

    # 2) solo hacia adelante
    if manifiesto.version != _INSTALADOR.match(manifiesto.archivo).group(1):
        return Resultado(False, "formato", "El nombre del instalador no coincide con su versión.")
    if tupla(manifiesto.version) <= tupla(version_actual):
        return Resultado(
            False, "no_es_nueva", f"La versión {manifiesto.version} no es más nueva que la instalada ({version_actual}).", manifiesto
        )

    # 3) integridad del instalador
    instalador = carpeta / manifiesto.archivo
    if not instalador.is_file() or instalador.stat().st_size != manifiesto.tamano:
        return Resultado(False, "archivo", "El instalador falta o no tiene el tamaño esperado.", manifiesto)
    if sha256_de(instalador) != manifiesto.sha256:
        return Resultado(False, "hash", "El instalador no coincide con el firmado: está dañado o fue alterado.", manifiesto)
    return Resultado(True, "ok", f"Actualización {manifiesto.version} verificada.", manifiesto, instalador)


Lanzador = Callable[[list[str]], None]


def _lanzar(argumentos: list[str]) -> None:
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP: sobrevive a la app
    subprocess.Popen(argumentos, close_fds=True, creationflags=flags)  # noqa: S603 - ejecutable verificado por firma y hash


def instalar(
    carpeta: str | Path, version_actual: str, datos_dir: Path, lanzador: Lanzador = _lanzar, clave_publica: str | None = None
) -> Resultado:
    """Verifica, copia el instalador a una carpeta privada, vuelve a verificar la COPIA y la ejecuta.

    Se ejecuta la copia verificada, no el archivo de la USB: asi nadie puede cambiarlo entre la
    comprobacion y la ejecucion.
    """
    r = verificar(carpeta, version_actual, clave_publica)
    if not r.ok:
        return r
    destino = Path(tempfile.mkdtemp(prefix="actualizacion_", dir=_carpeta_privada(datos_dir)))
    copia = destino / r.manifiesto.archivo
    shutil.copyfile(r.instalador, copia)
    if copia.stat().st_size != r.manifiesto.tamano or sha256_de(copia) != r.manifiesto.sha256:
        shutil.rmtree(destino, ignore_errors=True)
        return Resultado(False, "hash", "El instalador cambió mientras se copiaba: no se instalará.", r.manifiesto)
    lanzador([str(copia), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELANZAR=1"])
    return Resultado(True, "ok", f"Instalando la versión {r.manifiesto.version}…", r.manifiesto, copia)


def _carpeta_privada(datos_dir: Path) -> Path:
    p = datos_dir / "actualizaciones"
    p.mkdir(parents=True, exist_ok=True)
    return p


def unidades() -> list[Path]:
    """Letras de unidad disponibles (para buscar un paquete en una USB)."""
    if sys.platform != "win32":
        return []
    import ctypes

    mascara = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(f"{chr(65 + i)}:\\") for i in range(26) if mascara & (1 << i)]


def buscar_paquetes(raices: list[Path] | None = None) -> list[Path]:
    """Carpetas con un paquete en la raiz de cada unidad o en `TalentCV-Actualizacion`."""
    encontrados: list[Path] = []
    for raiz in raices if raices is not None else unidades():
        for candidata in (raiz / "TalentCV-Actualizacion", raiz):
            try:
                if (candidata / NOMBRE_MANIFIESTO).is_file():
                    encontrados.append(candidata)
                    break
            except OSError:  # unidad sin disco o sin permiso
                continue
    return encontrados
