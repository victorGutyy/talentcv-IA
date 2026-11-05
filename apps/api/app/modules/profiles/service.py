"""Logica de negocio de perfiles. No conoce HTTP."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.profiles.models import Profile
from app.modules.profiles.schemas import ProfileIn


class ProfileNotFound(Exception):
    pass


def _aplicar(profile: Profile, data: ProfileIn) -> None:
    for campo, valor in data.model_dump(exclude={"enlaces"}).items():
        setattr(profile, campo, valor)
    profile.enlaces = [e.model_dump() for e in data.enlaces]


def listar(db: Session) -> list[Profile]:
    return list(db.scalars(select(Profile).order_by(Profile.actualizado_en.desc(), Profile.id)))


def obtener(db: Session, profile_id: str) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFound(profile_id)
    return profile


def crear(db: Session, data: ProfileIn) -> Profile:
    profile = Profile()
    _aplicar(profile, data)
    db.add(profile)
    db.commit()
    return profile


def actualizar(db: Session, profile_id: str, data: ProfileIn) -> Profile:
    profile = obtener(db, profile_id)
    _aplicar(profile, data)
    db.commit()
    return profile


def duplicar(db: Session, profile_id: str) -> Profile:
    original = obtener(db, profile_id)
    copia = Profile()
    for campo in ("titular", "email", "telefono", "ciudad", "pais", "resumen"):
        setattr(copia, campo, getattr(original, campo))
    copia.nombre_completo = f"{original.nombre_completo} (copia)"[:200]
    copia.enlaces = [dict(e) for e in original.enlaces]
    db.add(copia)
    db.commit()
    return copia


def eliminar(db: Session, profile_id: str) -> None:
    profile = obtener(db, profile_id)
    db.delete(profile)
    db.commit()
