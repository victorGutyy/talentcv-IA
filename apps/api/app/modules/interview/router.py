"""Rutas del cuestionario adaptativo."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.extraction import review
from app.modules.interview import service
from app.modules.interview.service import EstadoEntrevista
from app.modules.profiles.models import Profile


class RespuestaIn(BaseModel):
    pregunta_id: str = Field(max_length=80)
    valores: dict[str, str | None] = Field(max_length=10)


class OmitirIn(BaseModel):
    pregunta_id: str = Field(max_length=80)


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api/perfiles/{profile_id}/entrevista", tags=["entrevista"])

    def _perfil(db: Session, profile_id: str) -> None:
        if db.get(Profile, profile_id) is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")

    def _gone() -> HTTPException:
        return HTTPException(
            status_code=409, detail="Esa pregunta ya no aplica. Se actualizó el cuestionario."
        )

    @router.get("", response_model=EstadoEntrevista)
    def ver(profile_id: str, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        return service.estado(db, profile_id)

    @router.post("/responder", response_model=EstadoEntrevista)
    def responder(profile_id: str, data: RespuestaIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        try:
            service.responder(db, profile_id, data.pregunta_id, {k: v for k, v in data.valores.items() if v})
        except service.QuestionGone:
            raise _gone() from None
        except review.FactValidationError as e:
            db.rollback()
            # Mismo formato de errores por campo que usa el resto de la API.
            raise HTTPException(
                status_code=422, detail=[{"loc": ["body", k], "msg": v} for k, v in e.errors.items()]
            ) from None
        except review.FactNotFound:
            raise _gone() from None
        return service.estado(db, profile_id)

    @router.post("/omitir", response_model=EstadoEntrevista)
    def omitir(profile_id: str, data: OmitirIn, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        try:
            service.omitir(db, profile_id, data.pregunta_id)
        except service.QuestionGone:
            raise _gone() from None
        return service.estado(db, profile_id)

    @router.post("/reiniciar", response_model=EstadoEntrevista)
    def reiniciar(profile_id: str, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        service.reiniciar(db, profile_id)
        return service.estado(db, profile_id)

    return router
