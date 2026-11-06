"""Copias de seguridad `.tcvbackup`: base de datos + documentos, con contrasena opcional.

Formato: un ZIP (`manifiesto.json`, `talentcv.sqlite3`, `documents/<id>.<ext>`) con el SHA-256 de cada archivo.
Con contrasena, el ZIP se cifra en bloques con XChaCha20-Poly1305 (libsodium) y la clave sale de Argon2id:
  TCVBENC1 | sal(16) | pasadas(u32) | memoria MiB(u32) | cabecera del flujo(24) | [largo(u32) bloque]…
El flujo detecta bloques alterados, reordenados o truncados.

Restaurar es la operacion mas delicada de la app: antes de tocar nada se valida el archivo por completo, se guarda
una copia del estado actual y, si algo falla a mitad, se vuelve atras.
"""

import hashlib
import json
import re
import shutil
import sqlite3
import struct
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import nacl.bindings as nb
import nacl.pwhash
import nacl.utils
from alembic.script import ScriptDirectory
from nacl.exceptions import CryptoError
from sqlalchemy import Engine

from app import __version__
from app.core.config import Settings
from app.core.db import MIGRATIONS_DIR, migrate
from app.core.errors import UserFacingError

MAGIA = b"TCVBENC1"
BLOQUE = 1024 * 1024
MAX_DESCOMPRIMIDO = 2 * 1024 * 1024 * 1024
MAX_ARCHIVO = 200 * 1024 * 1024
MAX_MEMORIA_MIB = 1024
_DOC = re.compile(r"^documents/[0-9a-f]{32}\.(pdf|docx|png|jpg)$")
_FIJOS = {"manifiesto.json", "talentcv.sqlite3"}
FORMATO = 1


class CopiaError(UserFacingError):
    pass


# ------------------------------------------------------------------ cifrado
def _clave(contrasena: str, sal: bytes, pasadas: int, mem_mib: int) -> bytes:
    return nacl.pwhash.argon2id.kdf(
        nb.crypto_secretstream_xchacha20poly1305_KEYBYTES,
        contrasena.encode("utf-8"),
        sal,
        opslimit=pasadas,
        memlimit=mem_mib * 1024 * 1024,
    )


def cifrar(origen: Path, destino: Path, contrasena: str) -> None:
    sal = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
    pasadas, mem_mib = nacl.pwhash.argon2id.OPSLIMIT_MODERATE, nacl.pwhash.argon2id.MEMLIMIT_MODERATE // (1024 * 1024)
    estado = nb.crypto_secretstream_xchacha20poly1305_state()
    cabecera = nb.crypto_secretstream_xchacha20poly1305_init_push(estado, _clave(contrasena, sal, pasadas, mem_mib))
    with origen.open("rb") as f, destino.open("wb") as out:
        out.write(MAGIA + sal + struct.pack("<II", pasadas, mem_mib) + cabecera)
        actual = f.read(BLOQUE)
        while True:
            siguiente = f.read(BLOQUE)
            etiqueta = (
                nb.crypto_secretstream_xchacha20poly1305_TAG_MESSAGE if siguiente else nb.crypto_secretstream_xchacha20poly1305_TAG_FINAL
            )
            cifrado = nb.crypto_secretstream_xchacha20poly1305_push(estado, actual, None, etiqueta)
            out.write(struct.pack("<I", len(cifrado)) + cifrado)
            if not siguiente:
                break
            actual = siguiente


def descifrar(origen: Path, destino: Path, contrasena: str) -> None:
    mal = CopiaError("La contraseña es incorrecta o el archivo está dañado.")
    with origen.open("rb") as f:
        cabecera_fija = f.read(len(MAGIA) + 16 + 8 + nb.crypto_secretstream_xchacha20poly1305_HEADERBYTES)
        if len(cabecera_fija) < len(MAGIA) + 16 + 8 + nb.crypto_secretstream_xchacha20poly1305_HEADERBYTES:
            raise CopiaError("El archivo de la copia está dañado o incompleto.")
        sal = cabecera_fija[8:24]
        pasadas, mem_mib = struct.unpack("<II", cabecera_fija[24:32])
        if not (1 <= pasadas <= 12 and 8 <= mem_mib <= MAX_MEMORIA_MIB):  # una cabecera manipulada no puede agotar la memoria
            raise CopiaError("El archivo de la copia está dañado.")
        estado = nb.crypto_secretstream_xchacha20poly1305_state()
        try:
            nb.crypto_secretstream_xchacha20poly1305_init_pull(estado, cabecera_fija[32:], _clave(contrasena, sal, pasadas, mem_mib))
        except (CryptoError, ValueError):
            raise mal from None
        final = False
        with destino.open("wb") as out:
            while True:
                pref = f.read(4)
                if not pref:
                    break
                if final or len(pref) < 4:
                    raise CopiaError("El archivo de la copia está dañado.")
                (largo,) = struct.unpack("<I", pref)
                bloque = f.read(largo) if 17 <= largo <= BLOQUE + 64 else b""
                if len(bloque) != largo:
                    raise CopiaError("El archivo de la copia está dañado o incompleto.")
                try:
                    texto, etiqueta = nb.crypto_secretstream_xchacha20poly1305_pull(estado, bloque, None)
                except CryptoError:
                    raise mal from None
                out.write(texto)
                final = etiqueta == nb.crypto_secretstream_xchacha20poly1305_TAG_FINAL
        if not final:
            raise CopiaError("El archivo de la copia está incompleto (se cortó).")


def esta_cifrada(archivo: Path) -> bool:
    with archivo.open("rb") as f:
        return f.read(len(MAGIA)) == MAGIA


# ------------------------------------------------------------------ crear
def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for b in iter(lambda: f.read(BLOQUE), b""):
            h.update(b)
    return h.hexdigest()


def _snapshot_db(origen: Path, destino: Path) -> None:
    """Copia consistente de la base de datos aunque la app este escribiendo (API de respaldo de SQLite)."""
    src = sqlite3.connect(f"file:{origen.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _consulta(db: Path, sql: str, todas: bool = False):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        cur = con.execute(sql)
        return cur.fetchall() if todas else cur.fetchone()
    finally:
        con.close()  # sin cerrar, Windows no deja borrar la carpeta temporal


def crear(settings: Settings, destino: Path, contrasena: str | None = None) -> dict:
    """Escribe la copia en `destino` y devuelve un resumen."""
    if not settings.db_path.exists():
        raise CopiaError("Todavía no hay datos que copiar.")
    with tempfile.TemporaryDirectory(prefix="copia_", dir=settings.data_dir) as t:
        tmp = Path(t)
        db = tmp / "talentcv.sqlite3"
        _snapshot_db(settings.db_path, db)
        docs = sorted(p for p in settings.documents_dir.glob("*") if p.is_file()) if settings.documents_dir.exists() else []
        archivos = {"talentcv.sqlite3": db} | {f"documents/{p.name}": p for p in docs if _DOC.match(f"documents/{p.name}")}
        manifiesto = {
            "formato": FORMATO,
            "app_version": __version__,
            "esquema": (_consulta(db, "SELECT version_num FROM alembic_version") or [None])[0],
            "creada": datetime.now().isoformat(timespec="seconds"),
            "perfiles": _consulta(db, "SELECT COUNT(*) FROM profiles")[0],
            "documentos": len(archivos) - 1,
            "archivos": [{"ruta": n, "sha256": _sha256(p), "tamano": p.stat().st_size} for n, p in archivos.items()],
        }
        zip_ruta = tmp / "copia.zip"
        with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False, indent=1))
            for nombre, p in archivos.items():
                z.write(p, nombre)
        if contrasena:
            cifrar(zip_ruta, destino, contrasena)
        else:
            shutil.copyfile(zip_ruta, destino)
    return {k: manifiesto[k] for k in ("app_version", "esquema", "creada", "perfiles", "documentos")} | {"cifrada": bool(contrasena)}


# ------------------------------------------------------------------ restaurar
def _validar_zip(z: zipfile.ZipFile) -> dict:
    """Nombres permitidos, tamanos acotados y hashes coincidentes: antes de extraer nada."""
    total = 0
    for info in z.infolist():
        nombre = info.filename
        if info.is_dir() or not (nombre in _FIJOS or _DOC.match(nombre)):
            raise CopiaError(f"La copia contiene un archivo no permitido: {nombre[:60]!r}.")
        if info.file_size > MAX_ARCHIVO:
            raise CopiaError("La copia contiene un archivo demasiado grande.")
        total += info.file_size
        if total > MAX_DESCOMPRIMIDO:
            raise CopiaError("La copia es demasiado grande.")
    try:
        manifiesto = json.loads(z.read("manifiesto.json"))
        esperados = {a["ruta"]: a for a in manifiesto["archivos"]}
    except (KeyError, ValueError, TypeError):
        raise CopiaError("La copia no tiene un manifiesto válido.") from None
    if manifiesto.get("formato") != FORMATO:
        raise CopiaError("La copia es de un formato que esta versión no reconoce.")
    if set(esperados) != set(z.namelist()) - {"manifiesto.json"} or "talentcv.sqlite3" not in esperados:
        raise CopiaError("La copia está incompleta o tiene archivos de más.")
    return manifiesto


def _extraer(z: zipfile.ZipFile, manifiesto: dict, destino: Path) -> None:
    for nombre, meta in {a["ruta"]: a for a in manifiesto["archivos"]}.items():
        ruta = destino / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        with z.open(nombre) as f, ruta.open("wb") as out:
            for b in iter(lambda: f.read(BLOQUE), b""):
                h.update(b)
                out.write(b)
        if h.hexdigest() != meta["sha256"] or ruta.stat().st_size != meta["tamano"]:
            raise CopiaError(f"La copia está dañada o fue alterada ({nombre}).")


def _comprobar_base(db: Path) -> str:
    try:
        if _consulta(db, "PRAGMA integrity_check")[0] != "ok":
            raise CopiaError("La base de datos de la copia está dañada.")
        tablas = {r[0] for r in _consulta(db, "SELECT name FROM sqlite_master WHERE type='table'", todas=True)}
        rev = _consulta(db, "SELECT version_num FROM alembic_version") if "alembic_version" in tablas else None
    except sqlite3.DatabaseError:
        raise CopiaError("La base de datos de la copia no es válida.") from None
    if not {"profiles", "alembic_version"} <= tablas or not rev:
        raise CopiaError("La base de datos de la copia no es válida.")
    try:
        conocida = ScriptDirectory(str(MIGRATIONS_DIR)).get_revision(rev[0]) is not None
    except Exception:  # Alembic lanza una excepcion si no conoce la revision
        conocida = False
    if not conocida:
        raise CopiaError("Esta copia se hizo con una versión MÁS NUEVA de TalentCV AI. Actualiza la aplicación y vuelve a intentarlo.")
    return rev[0]


def restaurar(settings: Settings, engine: Engine, archivo: Path, contrasena: str | None, hay_tareas_activas: bool) -> dict:
    if hay_tareas_activas:
        raise CopiaError("Hay tareas en curso. Espera a que terminen o cancélalas antes de restaurar.")
    with tempfile.TemporaryDirectory(prefix="restauracion_", dir=settings.data_dir) as t:
        tmp = Path(t)
        zip_ruta = archivo
        if esta_cifrada(archivo):
            if not contrasena:
                raise CopiaError("La copia está protegida: escribe su contraseña.")
            zip_ruta = tmp / "descifrada.zip"
            descifrar(archivo, zip_ruta, contrasena)
        try:
            with zipfile.ZipFile(zip_ruta) as z:
                manifiesto = _validar_zip(z)
                nuevo = tmp / "nuevo"
                _extraer(z, manifiesto, nuevo)
        except zipfile.BadZipFile:
            raise CopiaError("El archivo no es una copia de TalentCV AI válida.") from None
        _comprobar_base(nuevo / "talentcv.sqlite3")

        # --- todo validado: guardar el estado actual y reemplazar
        previa = settings.backups_dir / f"antes-de-restaurar-{datetime.now():%Y%m%d-%H%M%S}"
        previa.mkdir(parents=True, exist_ok=True)
        if settings.db_path.exists():
            _snapshot_db(settings.db_path, previa / "talentcv.sqlite3")
        if settings.documents_dir.exists():
            shutil.copytree(settings.documents_dir, previa / "documents")
        engine.dispose()
        try:
            for sufijo in ("", "-wal", "-shm"):
                Path(str(settings.db_path) + sufijo).unlink(missing_ok=True)
            shutil.copyfile(nuevo / "talentcv.sqlite3", settings.db_path)
            if settings.documents_dir.exists():
                shutil.rmtree(settings.documents_dir)
            if (nuevo / "documents").exists():
                shutil.copytree(nuevo / "documents", settings.documents_dir)
            migrate(settings)  # sube de esquema si la copia era de una version anterior
        except Exception:
            _volver_atras(settings, engine, previa)
            raise CopiaError("No se pudo restaurar la copia; se dejaron tus datos como estaban.") from None
    return {
        "perfiles": manifiesto["perfiles"],
        "documentos": manifiesto["documentos"],
        "copia_previa": str(previa),
        "creada": manifiesto["creada"],
    }


def _volver_atras(settings: Settings, engine: Engine, previa: Path) -> None:
    engine.dispose()
    for sufijo in ("", "-wal", "-shm"):
        Path(str(settings.db_path) + sufijo).unlink(missing_ok=True)
    if (previa / "talentcv.sqlite3").exists():
        shutil.copyfile(previa / "talentcv.sqlite3", settings.db_path)
    if settings.documents_dir.exists():
        shutil.rmtree(settings.documents_dir, ignore_errors=True)
    if (previa / "documents").exists():
        shutil.copytree(previa / "documents", settings.documents_dir)
