"""Rutas de sistema: version, copias de seguridad y actualizaciones."""

import os
import sys
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from starlette.background import BackgroundTask

from app import __version__
from app.core.config import Settings
from app.core.errors import UserFacingError
from app.orchestrator.jobs import JobManager
from app.orchestrator.models import ACTIVE
from app.system import actualizaciones, copias

MAX_COPIA_SUBIDA = 1024 * 1024 * 1024


class VersionOut(BaseModel):
    version: str
    datos: str
    empaquetado: bool


class CopiaIn(BaseModel):
    contrasena: str | None = Field(default=None, max_length=200)


class RutaIn(BaseModel):
    ruta: str = Field(min_length=1, max_length=500)


class PaqueteOut(BaseModel):
    ruta: str
    ok: bool
    motivo: str
    mensaje: str
    version: str | None = None
    notas: str | None = None
    fecha: str | None = None


def _borrar(ruta: Path) -> None:
    """Borra un temporal sin que un fallo (archivo aun en uso) rompa la respuesta."""
    try:
        ruta.unlink(missing_ok=True)
    except OSError:
        pass


def _paquete(ruta: Path, r: actualizaciones.Resultado) -> PaqueteOut:
    m = r.manifiesto
    return PaqueteOut(
        ruta=str(ruta), ok=r.ok, motivo=r.motivo, mensaje=r.mensaje,
        version=m.version if m else None, notas=m.notas if m else None, fecha=m.fecha if m else None,
    )


def build_router(settings: Settings, engine: Engine, jobs: JobManager) -> APIRouter:
    router = APIRouter(prefix="/api/sistema", tags=["sistema"])

    def _carpeta(ruta: str) -> Path:
        p = Path(ruta)
        if not p.is_dir():
            raise HTTPException(status_code=422, detail="Esa carpeta no existe o no se puede abrir.")
        return p

    @router.get("/version", response_model=VersionOut)
    def version():
        return VersionOut(version=__version__, datos=str(settings.data_dir), empaquetado=bool(getattr(sys, "frozen", False)))

    # ---------------------------------------------------------------- copias
    @router.post("/copia")
    def crear_copia(data: CopiaIn):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        fd, nombre_tmp = tempfile.mkstemp(prefix="copia_", suffix=".tcvbackup", dir=settings.data_dir)
        os.close(fd)  # si no se cierra, Windows no deja borrar el archivo
        tmp = Path(nombre_tmp)
        try:
            copias.crear(settings, tmp, (data.contrasena or None))
        except UserFacingError as e:
            _borrar(tmp)
            raise HTTPException(status_code=409, detail=str(e)) from None
        nombre = f"TalentCV_copia_{datetime.now():%Y%m%d_%H%M}.tcvbackup"
        return FileResponse(
            tmp,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"},
            background=BackgroundTask(_borrar, tmp),
        )

    @router.post("/restaurar")
    async def restaurar(request: Request):
        # La contrasena viaja en una cabecera (no en la URL: las URL quedan en registros).
        contrasena = urllib.parse.unquote(request.headers.get("x-tcv-contrasena", "")) or None
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        fd, nombre = tempfile.mkstemp(prefix="subida_", suffix=".tcvbackup", dir=settings.data_dir)
        tmp = Path(nombre)  # `open(fd)` de abajo se encarga de cerrar el descriptor
        try:
            total = 0
            with open(fd, "wb") as out:
                async for parte in request.stream():
                    total += len(parte)
                    if total > MAX_COPIA_SUBIDA:
                        raise HTTPException(status_code=422, detail="La copia es demasiado grande.")
                    out.write(parte)
            if total == 0:
                raise HTTPException(status_code=422, detail="No se recibió ningún archivo.")
            activas = any(j.status in ACTIVE for j in jobs.recent(100))
            try:
                return await run_in_threadpool(copias.restaurar, settings, engine, tmp, contrasena, activas)
            except UserFacingError as e:
                raise HTTPException(status_code=422, detail=str(e)) from None
        finally:
            _borrar(tmp)

    # ---------------------------------------------------------------- actualizaciones
    @router.get("/actualizaciones/buscar", response_model=list[PaqueteOut])
    def buscar():
        return [_paquete(c, actualizaciones.verificar(c, __version__)) for c in actualizaciones.buscar_paquetes()]

    @router.post("/actualizaciones/verificar", response_model=PaqueteOut)
    def verificar(data: RutaIn):
        carpeta = _carpeta(data.ruta)
        return _paquete(carpeta, actualizaciones.verificar(carpeta, __version__))

    @router.post("/actualizaciones/instalar", response_model=PaqueteOut)
    def instalar(data: RutaIn):
        carpeta = _carpeta(data.ruta)
        r = actualizaciones.instalar(carpeta, __version__, settings.data_dir, lanzador=actualizaciones._lanzar)
        if not r.ok:
            raise HTTPException(status_code=422, detail=r.mensaje)
        return _paquete(carpeta, r)

    return router
