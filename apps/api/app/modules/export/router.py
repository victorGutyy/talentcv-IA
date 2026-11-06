"""Rutas de plantillas y exportacion del curriculum."""

import re
import unicodedata
from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.export import cv as cv_mod
from app.modules.export.docx_render import render_docx
from app.modules.export.plantillas import PAPELES, PLANTILLAS, Plantilla
from app.modules.profiles.models import Profile

TIPOS = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


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


def nombre_archivo(nombre: str, plantilla: str, formato: str) -> str:
    """Solo ASCII: sin acentos, espacios ni caracteres peligrosos."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_") or "Curriculum"
    return f"CV_{base[:60]}_{plantilla}.{formato}"


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
        plantilla = PLANTILLAS.get(data.plantilla)
        if plantilla is None:
            raise HTTPException(status_code=422, detail="Plantilla desconocida.")
        if data.papel not in PAPELES:
            raise HTTPException(status_code=422, detail="Tamaño de papel desconocido.")
        cv = cv_mod.sanear(cv_mod.construir(db, profile_id).cv)
        if data.formato == "docx":
            contenido = render_docx(cv, plantilla, data.papel)
        else:
            try:
                from app.modules.export.pdf_render import render_pdf
            except ImportError:
                raise HTTPException(
                    status_code=501, detail="La exportación a PDF no está disponible en esta instalación."
                ) from None
            contenido = render_pdf(cv, plantilla, data.papel)
        archivo = nombre_archivo(perfil.nombre_completo, plantilla.id, data.formato)
        return Response(
            content=contenido,
            media_type=TIPOS[data.formato],
            headers={"Content-Disposition": f'attachment; filename="{archivo}"', "Cache-Control": "no-store"},
        )

    return router
