"""Rutas de redaccion: pedir borradores a la IA, revisarlos y analizar una oferta."""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.profiles.models import Profile
from app.modules.writing import keywords, service
from app.modules.writing.models import Draft
from app.modules.writing.prompts import MAX_OBJETIVO
from app.orchestrator.jobs import JobManager
from app.orchestrator.router import TareaOut
from app.orchestrator.router import _out as tarea_out


class RedaccionIn(BaseModel):
    puesto_objetivo: str | None = Field(default=None, max_length=MAX_OBJETIVO)


class BorradorOut(BaseModel):
    id: str
    perfil_id: str
    seccion: str
    puesto_id: str | None
    fuentes: list[str]
    texto: str
    origen: str
    estado: str
    auditoria_ok: bool
    problemas: list[dict]
    avisos: list[str]
    actualizado_en: datetime


class AccionBorrador(BaseModel):
    accion: Literal["aprobar", "rechazar", "restaurar", "editar"]
    texto: str | None = Field(default=None, max_length=5000)


class OfertaIn(BaseModel):
    oferta: str = Field(min_length=3, max_length=keywords.MAX_OFERTA)


class ComparacionOut(BaseModel):
    coinciden: list[str]
    faltan: list[str]


def _out(d: Draft) -> BorradorOut:
    return BorradorOut(
        id=d.id,
        perfil_id=d.profile_id,
        seccion=d.section,
        puesto_id=d.target_fact_id,
        fuentes=d.source_ids,
        texto=d.text,
        origen=d.origin,
        estado=d.status,
        auditoria_ok=d.audit_ok,
        problemas=d.audit_issues,
        avisos=d.audit_warnings,
        actualizado_en=d.updated_at,
    )


def build_router(get_session: Callable[..., Session], jobs: JobManager) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["redaccion"])

    def _perfil(db: Session, profile_id: str) -> None:
        if db.get(Profile, profile_id) is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")

    @router.post(
        "/perfiles/{profile_id}/redaccion", response_model=TareaOut, status_code=status.HTTP_202_ACCEPTED
    )
    async def redactar(profile_id: str, data: RedaccionIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        if not service.cargar(db, profile_id).hay_datos:
            raise HTTPException(
                status_code=409,
                detail="Primero aprueba algunos datos en «Revisar datos»: la redacción solo usa información aprobada.",
            )
        job = jobs.submit(
            "redactar_perfil", {"perfil_id": profile_id, "puesto_objetivo": data.puesto_objetivo}
        )
        return tarea_out(job)

    @router.get("/perfiles/{profile_id}/borradores", response_model=list[BorradorOut])
    def listar(profile_id: str, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        return [_out(d) for d in service.listar(db, profile_id)]

    @router.patch("/borradores/{draft_id}", response_model=BorradorOut)
    def actuar(draft_id: str, data: AccionBorrador, db: Session = Depends(get_session)):
        try:
            d = service.get(db, draft_id)
            service.actuar(db, d, data.accion, data.texto)
        except service.DraftNotFound:
            raise HTTPException(status_code=404, detail="Borrador no encontrado") from None
        except service.DraftBlocked:
            raise HTTPException(
                status_code=409,
                detail="La auditoría encontró contenido que no está en tus datos. Edita el texto o recházalo.",
            ) from None
        except service.DraftInvalid as e:
            db.rollback()
            raise HTTPException(
                status_code=422, detail=[{"loc": ["body", k], "msg": v} for k, v in e.errors.items()]
            ) from None
        return _out(d)

    @router.delete("/borradores/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
    def eliminar(draft_id: str, db: Session = Depends(get_session)):
        try:
            db.delete(service.get(db, draft_id))
        except service.DraftNotFound:
            raise HTTPException(status_code=404, detail="Borrador no encontrado") from None
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/perfiles/{profile_id}/palabras-clave", response_model=ComparacionOut)
    def palabras_clave(profile_id: str, data: OfertaIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        material = service.cargar(db, profile_id)
        return keywords.comparar(data.oferta, service.fuentes_resumen(material))

    return router
