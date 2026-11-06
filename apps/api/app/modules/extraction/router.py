"""Rutas de consulta de datos extraidos (la confirmacion llega en la Fase 4)."""

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.modules.extraction import service
from app.modules.profiles.models import Profile


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str
    category: str
    data: dict
    quote: str
    page: int | None
    dropped_fields: list[str]
    from_ocr: bool
    status: str
    created_at: datetime


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["extraccion"])

    @router.get("/perfiles/{profile_id}/hechos", response_model=list[FactOut])
    def listar_hechos(
        profile_id: str,
        documento: str | None = Query(default=None, max_length=32),
        estado: str | None = Query(default=None, max_length=12),
        db: Session = Depends(get_session),
    ):
        if db.get(Profile, profile_id) is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        return service.list_facts(db, profile_id, documento, estado)

    return router
