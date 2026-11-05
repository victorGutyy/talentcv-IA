"""Rutas HTTP de perfiles."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.modules.profiles import service
from app.modules.profiles.schemas import ProfileIn, ProfileOut, ProfileSummary


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api/perfiles", tags=["perfiles"])

    def _o404(fn, *args):
        try:
            return fn(*args)
        except service.ProfileNotFound:
            raise HTTPException(status_code=404, detail="Perfil no encontrado") from None

    @router.get("", response_model=list[ProfileSummary])
    def listar(db: Session = Depends(get_session)):
        return service.listar(db)

    @router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
    def crear(data: ProfileIn, db: Session = Depends(get_session)):
        return service.crear(db, data)

    @router.get("/{profile_id}", response_model=ProfileOut)
    def obtener(profile_id: str, db: Session = Depends(get_session)):
        return _o404(service.obtener, db, profile_id)

    @router.put("/{profile_id}", response_model=ProfileOut)
    def actualizar(profile_id: str, data: ProfileIn, db: Session = Depends(get_session)):
        return _o404(service.actualizar, db, profile_id, data)

    @router.post("/{profile_id}/duplicar", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
    def duplicar(profile_id: str, db: Session = Depends(get_session)):
        return _o404(service.duplicar, db, profile_id)

    @router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
    def eliminar(profile_id: str, db: Session = Depends(get_session)):
        _o404(service.eliminar, db, profile_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
