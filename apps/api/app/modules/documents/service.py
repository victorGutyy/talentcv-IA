"""Logica de documentos: guardado seguro, listado y borrado. No conoce HTTP."""

import contextlib
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.documents.files import (
    EXTENSION,
    InvalidFile,
    detect_kind,
    image_extension,
    safe_display_name,
)
from app.modules.documents.models import PAGE_SEP, Document
from app.modules.extraction.service import delete_unapproved_for_document
from app.modules.profiles.models import Profile


class DocumentNotFound(Exception):
    pass


class ProfileMissing(Exception):
    pass


class DuplicateDocument(Exception):
    def __init__(self, existing_id: str):
        self.existing_id = existing_id


def path_of(settings: Settings, doc: Document):
    return settings.documents_dir / doc.stored_name


def create(db: Session, settings: Settings, profile_id: str, original_name: str, data: bytes) -> Document:
    if db.get(Profile, profile_id) is None:
        raise ProfileMissing(profile_id)
    if not data:
        raise InvalidFile("El archivo está vacío.")
    if len(data) > settings.max_upload_bytes:
        raise InvalidFile(f"El archivo supera el máximo de {settings.max_upload_bytes // (1024 * 1024)} MB.")
    kind = detect_kind(data)

    digest = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(Document).where(Document.profile_id == profile_id, Document.sha256 == digest))
    if dup is not None:
        raise DuplicateDocument(dup.id)

    doc_id = uuid.uuid4().hex
    ext = image_extension(data) if kind == "image" else EXTENSION[kind]
    stored = f"{doc_id}.{ext}"  # nombre generado: el del usuario nunca toca el disco
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    (settings.documents_dir / stored).write_bytes(data)

    doc = Document(
        id=doc_id,
        profile_id=profile_id,
        original_name=safe_display_name(original_name),
        stored_name=stored,
        kind=kind,
        size_bytes=len(data),
        sha256=digest,
    )
    db.add(doc)
    db.commit()
    return doc


def get(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise DocumentNotFound(doc_id)
    return doc


def list_for_profile(db: Session, profile_id: str) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(Document.profile_id == profile_id).order_by(Document.created_at.desc())
        )
    )


def pages_of(doc: Document) -> list[str]:
    return doc.text.split(PAGE_SEP) if doc.text else []


def _remove_file(settings: Settings, doc: Document) -> None:
    with contextlib.suppress(FileNotFoundError):
        path_of(settings, doc).unlink()


def delete(db: Session, settings: Settings, doc_id: str) -> None:
    """Borra el documento y los datos SIN aprobar. Los aprobados por el usuario se conservan."""
    doc = get(db, doc_id)
    _remove_file(settings, doc)
    delete_unapproved_for_document(db, doc_id)
    db.delete(doc)
    db.commit()


def purge_profile_files(db: Session, settings: Settings, profile_id: str) -> None:
    """Se llama antes de borrar un perfil: las filas caen en cascada, los archivos no."""
    for doc in list_for_profile(db, profile_id):
        _remove_file(settings, doc)
