"""Rutas de datos extraidos y su revision por el usuario."""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.modules.extraction import review, service
from app.modules.extraction.models import STATUSES
from app.modules.profiles.models import Profile


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str | None
    origin: str
    category: str
    data: dict
    original_data: dict | None
    quote: str
    page: int | None
    dropped_fields: list[str]
    from_ocr: bool
    status: str
    created_at: datetime
    updated_at: datetime


class AccionIn(BaseModel):
    accion: Literal["confirmar", "rechazar", "restaurar", "editar"]
    datos: dict | None = None


class ManualIn(BaseModel):
    categoria: str = Field(max_length=20)
    datos: dict


class LoteIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    accion: Literal["confirmar", "rechazar", "restaurar"]


class LoteOut(BaseModel):
    actualizados: int
    ignorados: int


def _validation_http_error(e: review.FactValidationError) -> HTTPException:
    # Mismo formato que los errores de validacion de FastAPI: la interfaz los asocia a cada campo.
    return HTTPException(
        status_code=422, detail=[{"loc": ["body", k], "msg": v} for k, v in e.errors.items()]
    )


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["extraccion"])

    def _perfil(db: Session, profile_id: str) -> None:
        if db.get(Profile, profile_id) is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")

    @router.get("/perfiles/{profile_id}/hechos", response_model=list[FactOut])
    def listar_hechos(
        profile_id: str,
        documento: str | None = Query(default=None, max_length=32),
        estado: str | None = Query(
            default=None, max_length=60, description="uno o varios, separados por coma"
        ),
        db: Session = Depends(get_session),
    ):
        _perfil(db, profile_id)
        estados = [e.strip() for e in estado.split(",")] if estado else None
        if estados and any(e not in STATUSES for e in estados):
            raise HTTPException(status_code=422, detail="Estado no válido.")
        return service.list_facts(db, profile_id, documento, estados)

    @router.post("/perfiles/{profile_id}/hechos", response_model=FactOut, status_code=status.HTTP_201_CREATED)
    def agregar_dato_propio(profile_id: str, data: ManualIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        try:
            return review.crear_manual(db, profile_id, data.categoria, data.datos)
        except review.FactValidationError as e:
            raise _validation_http_error(e) from None

    @router.post("/perfiles/{profile_id}/hechos/lote", response_model=LoteOut)
    def lote(profile_id: str, data: LoteIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        return review.aplicar_lote(db, profile_id, data.ids, data.accion)

    @router.patch("/hechos/{fact_id}", response_model=FactOut)
    def revisar(fact_id: str, data: AccionIn, db: Session = Depends(get_session)):
        try:
            fact = review.get_fact(db, fact_id)
        except review.FactNotFound:
            raise HTTPException(status_code=404, detail="Dato no encontrado") from None
        try:
            if data.accion == "editar":
                review.editar(fact, data.datos or {})
            else:
                {"confirmar": review.confirmar, "rechazar": review.rechazar, "restaurar": review.restaurar}[
                    data.accion
                ](fact)
        except review.FactValidationError as e:
            db.rollback()
            raise _validation_http_error(e) from None
        db.commit()
        return fact

    return router
