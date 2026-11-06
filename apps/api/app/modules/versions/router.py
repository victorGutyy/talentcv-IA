"""Rutas del historial de versiones."""

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.export import cv as cv_mod
from app.modules.export.archivo import ExportError, generar, nombre_archivo
from app.modules.export.cv import CV
from app.modules.export.router import ExportarIn, respuesta_archivo
from app.modules.profiles.models import Profile
from app.modules.versions import diff, service
from app.modules.versions.models import CVVersion


class ResumenVersion(BaseModel):
    puestos: int
    puntos: int
    habilidades: int
    tiene_resumen: bool


class VersionOut(BaseModel):
    id: str
    perfil_id: str
    numero: int
    etiqueta: str | None
    origen: str
    creada_en: datetime
    exportaciones: list[dict]
    contenido: ResumenVersion


class VersionDetalle(VersionOut):
    cv: CV


class GuardarIn(BaseModel):
    etiqueta: str | None = Field(default=None, max_length=80)


class GuardarOut(BaseModel):
    version: VersionOut
    creada: bool


class EtiquetaIn(BaseModel):
    etiqueta: str | None = Field(default=None, max_length=80)


class ComparacionOut(BaseModel):
    antes: str  # «Versión 2»
    despues: str  # «Versión 3» o «Estado actual»
    iguales: bool
    cambios: list[diff.Cambio]


def _out(v: CVVersion) -> VersionOut:
    cv = service.contenido(v)
    return VersionOut(
        id=v.id,
        perfil_id=v.profile_id,
        numero=v.numero,
        etiqueta=v.etiqueta,
        origen=v.origen,
        creada_en=v.created_at,
        exportaciones=v.exportaciones,
        contenido=ResumenVersion(
            puestos=len(cv.experiencia),
            puntos=sum(len(p.puntos) for p in cv.experiencia),
            habilidades=len(cv.habilidades),
            tiene_resumen=bool(cv.resumen),
        ),
    )


def build_router(get_session: Callable[..., Session]) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["versiones"])

    def _perfil(db: Session, profile_id: str) -> Profile:
        p = db.get(Profile, profile_id)
        if p is None:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        return p

    def _version(db: Session, version_id: str) -> CVVersion:
        try:
            return service.get(db, version_id)
        except service.VersionNotFound:
            raise HTTPException(status_code=404, detail="Versión no encontrada") from None

    @router.get("/perfiles/{profile_id}/versiones", response_model=list[VersionOut])
    def listar(profile_id: str, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        return [_out(v) for v in service.listar(db, profile_id)]

    @router.post("/perfiles/{profile_id}/versiones", response_model=GuardarOut)
    def guardar(profile_id: str, data: GuardarIn, response: Response, db: Session = Depends(get_session)):
        _perfil(db, profile_id)
        cv = cv_mod.sanear(cv_mod.construir(db, profile_id).cv)
        etiqueta = (data.etiqueta or "").strip() or None
        v, creada = service.guardar(db, profile_id, cv, "manual", etiqueta)
        response.status_code = status.HTTP_201_CREATED if creada else status.HTTP_200_OK
        return GuardarOut(version=_out(v), creada=creada)

    @router.get("/versiones/{version_id}", response_model=VersionDetalle)
    def ver(version_id: str, db: Session = Depends(get_session)):
        v = _version(db, version_id)
        return VersionDetalle(**_out(v).model_dump(), cv=service.contenido(v))

    @router.patch("/versiones/{version_id}", response_model=VersionOut)
    def renombrar(version_id: str, data: EtiquetaIn, db: Session = Depends(get_session)):
        v = _version(db, version_id)
        service.renombrar(db, v, data.etiqueta)
        return _out(v)

    @router.delete("/versiones/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
    def eliminar(version_id: str, db: Session = Depends(get_session)):
        service.eliminar(db, _version(db, version_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/versiones/{version_id}/comparar", response_model=ComparacionOut)
    def comparar(version_id: str, con: str = "actual", db: Session = Depends(get_session)):
        a = _version(db, version_id)
        if con == "actual":
            b_cv, b_nombre = cv_mod.sanear(cv_mod.construir(db, a.profile_id).cv), "Estado actual"
        else:
            b = _version(db, con)
            if b.profile_id != a.profile_id:
                raise HTTPException(status_code=422, detail="Las versiones son de perfiles distintos.")
            b_cv, b_nombre = service.contenido(b), f"Versión {b.numero}"
        cambios = diff.comparar(service.contenido(a), b_cv)
        return ComparacionOut(
            antes=f"Versión {a.numero}", despues=b_nombre, iguales=not cambios, cambios=cambios
        )

    @router.post("/versiones/{version_id}/exportar")
    def reexportar(version_id: str, data: ExportarIn, db: Session = Depends(get_session)):
        """Vuelve a generar el archivo EXACTO de esa version, sin depender de los datos actuales."""
        v = _version(db, version_id)
        perfil = db.get(Profile, v.profile_id)
        try:
            contenido = generar(cv_mod.sanear(service.contenido(v)), data.plantilla, data.formato, data.papel)
        except ExportError as e:
            raise HTTPException(status_code=e.status, detail=str(e)) from None
        service.registrar_exportacion(db, v, data.plantilla, data.formato, data.papel)
        nombre = nombre_archivo(perfil.nombre_completo, data.plantilla, data.formato, v.numero)
        return respuesta_archivo(contenido, data.formato, nombre, v.numero, v.id)

    return router
