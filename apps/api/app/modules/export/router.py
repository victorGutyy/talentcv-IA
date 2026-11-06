"""Rutas de plantillas y exportacion del curriculum."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.export import cv as cv_mod
from app.modules.export.archivo import TIPOS, ExportError, generar, nombre_archivo
from app.modules.export.plantillas import PLANTILLAS, Plantilla
from app.modules.profiles.models import Profile
from app.modules.versions import service as versiones

__all__ = ["ExportarIn", "build_router", "nombre_archivo", "respuesta_archivo"]


class PlantillaOut(BaseModel):
    id: str
    nombre: str
    descripcion: str
    color: str | None
    fuente: str
    secciones: list[str]  # titulos, en el orden en que salen
    orden: list[str]  # ids de seccion en ese mismo orden
    titulos: dict[str, str]
    cabecera_centrada: bool
    linea_bajo_titulos: bool


class ExportarIn(BaseModel):
    plantilla: str
    formato: Literal["docx", "pdf"]
    papel: Literal["carta", "a4"] = "carta"


def _plantilla_out(p: Plantilla) -> PlantillaOut:
    return PlantillaOut(
        id=p.id,
        nombre=p.nombre,
        descripcion=p.descripcion,
        color="#{:02x}{:02x}{:02x}".format(*p.color) if p.color else None,
        fuente=p.fuente_docx,
        secciones=[p.titulo(s) for s in p.orden],
        orden=list(p.orden),
        titulos={s: p.titulo(s) for s in p.orden},
        cabecera_centrada=p.cabecera_centrada,
        linea_bajo_titulos=p.linea_bajo_titulos,
    )


def respuesta_archivo(
    contenido: bytes, formato: str, nombre: str, numero_version: int, version_id: str
) -> Response:
    return Response(
        content=contenido,
        media_type=TIPOS[formato],
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
            "X-Version-Number": str(numero_version),
            "X-Version-Id": version_id,
        },
    )


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["exportacion"])

    def _perfil(db: Session, profile_id: str) -> Profile:
        p = db.get(Profile, profile_id)
        if p is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        return p

    @router.get("/plantillas", response_model=list[PlantillaOut])
    def plantillas():
        return [_plantilla_out(p) for p in PLANTILLAS.values()]

    @router.get("/perfiles/{profile_id}/curriculum", response_model=cv_mod.Informe)
    def vista_previa(profile_id: str, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        return cv_mod.construir(db, profile_id)

    @router.post("/perfiles/{profile_id}/exportar")
    def exportar(profile_id: str, data: ExportarIn, db: Session = Depends(get_session)):
        perfil = _perfil(db, profile_id)
        cv = cv_mod.sanear(cv_mod.construir(db, profile_id).cv)
        try:
            contenido = generar(cv, data.plantilla, data.formato, data.papel)
        except ExportError as e:
            raise HTTPException(status_code=e.status, detail=str(e)) from None
        # Cada exportacion deja constancia: la version guarda el contenido exacto del archivo entregado.
        version, _ = versiones.guardar(db, profile_id, cv, "exportacion")
        versiones.registrar_exportacion(db, version, data.plantilla, data.formato, data.papel)
        archivo = nombre_archivo(perfil.nombre_completo, data.plantilla, data.formato)
        return respuesta_archivo(contenido, data.formato, archivo, version.numero, version.id)

    return router
