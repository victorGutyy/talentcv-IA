"""Logica del historial de versiones. Una version es una instantanea del contenido del curriculum:
la misma informacion aprobada produce la misma version (no se duplican)."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.export.cv import CV
from app.modules.versions.models import CVVersion


class VersionNotFound(Exception):
    pass


def hash_contenido(cv: CV) -> str:
    canonico = json.dumps(cv.model_dump(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def get(db: Session, version_id: str) -> CVVersion:
    v = db.get(CVVersion, version_id)
    if v is None:
        raise VersionNotFound(version_id)
    return v


def listar(db: Session, profile_id: str) -> list[CVVersion]:
    return list(
        db.scalars(
            select(CVVersion).where(CVVersion.profile_id == profile_id).order_by(CVVersion.numero.desc())
        )
    )


def contenido(v: CVVersion) -> CV:
    return CV.model_validate(
        v.cv
    )  # tolera versiones guardadas por una app anterior (campos con valor por defecto)


def guardar(
    db: Session, profile_id: str, cv: CV, origen: str, etiqueta: str | None = None
) -> tuple[CVVersion, bool]:
    """Guarda la instantanea si el contenido es nuevo. Devuelve (version, creada)."""
    h = hash_contenido(cv)
    existente = db.scalar(
        select(CVVersion).where(CVVersion.profile_id == profile_id, CVVersion.content_hash == h)
    )
    if existente is not None:
        if etiqueta and not existente.etiqueta:
            existente.etiqueta = etiqueta
            db.commit()
        return existente, False
    siguiente = (
        db.scalar(select(func.max(CVVersion.numero)).where(CVVersion.profile_id == profile_id)) or 0
    ) + 1
    v = CVVersion(
        profile_id=profile_id,
        numero=siguiente,
        etiqueta=etiqueta,
        origen=origen,
        content_hash=h,
        cv=cv.model_dump(),
        exportaciones=[],
    )
    db.add(v)
    db.commit()
    return v, True


def registrar_exportacion(db: Session, v: CVVersion, plantilla: str, formato: str, papel: str) -> None:
    v.exportaciones = [
        *v.exportaciones,
        {"plantilla": plantilla, "formato": formato, "papel": papel, "fecha": datetime.now(UTC).isoformat()},
    ]
    db.commit()


def renombrar(db: Session, v: CVVersion, etiqueta: str | None) -> None:
    v.etiqueta = (etiqueta or "").strip() or None
    db.commit()


def eliminar(db: Session, v: CVVersion) -> None:
    db.delete(v)
    db.commit()
