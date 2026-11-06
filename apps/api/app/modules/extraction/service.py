"""Logica de extraccion: fragmentado del texto y guardado de hechos verificados."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.extraction.evidence import Verified, fingerprint
from app.modules.extraction.models import ExtractedFact

CHUNK_CHARS = 4500  # ~1400 tokens: cabe con el prompt y la respuesta en num_ctx=4096


def chunk_pages(pages: list[str], max_chars: int = CHUNK_CHARS) -> list[str]:
    """Reparte el texto en fragmentos por lineas, sin partir lineas salvo que sean enormes."""
    lines: list[str] = []
    for page in pages:
        for line in page.split("\n"):
            while len(line) > max_chars:  # linea gigante (OCR sin saltos)
                lines.append(line[:max_chars])
                line = line[max_chars:]
            lines.append(line)
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > max_chars and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return [c for c in chunks if c.strip()]


def save_facts(
    db: Session,
    profile_id: str,
    document_id: str,
    facts: list[Verified],
    ocr_pages: list[int] | None = None,
) -> int:
    """Reemplaza los hechos PENDIENTES del documento. Los ya confirmados no se tocan ni se duplican."""
    db.execute(
        delete(ExtractedFact).where(
            ExtractedFact.document_id == document_id, ExtractedFact.status == "pendiente"
        )
    )
    seen: set[str] = set()
    # Se consideran TODOS los estados: un dato rechazado no debe reaparecer al re-extraer, y uno
    # editado tampoco debe volver con su valor original (p. ej. el correo mal leido por el OCR).
    for f in db.scalars(select(ExtractedFact).where(ExtractedFact.profile_id == profile_id)):
        seen.add(fingerprint(f.category, f.data))
        if f.original_data:
            seen.add(fingerprint(f.category, f.original_data))
    saved = 0
    for v in facts:
        key = fingerprint(v.category, v.data)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            ExtractedFact(
                profile_id=profile_id,
                document_id=document_id,
                category=v.category,
                data=v.data,
                quote=v.quote,
                page=v.page,
                dropped_fields=v.dropped_fields,
                from_ocr=v.page in (ocr_pages or []),
            )
        )
        saved += 1
    db.commit()
    return saved


def delete_unapproved_for_document(db: Session, document_id: str) -> None:
    """Al borrar un documento se van sus datos sin aprobar; los aprobados quedan (document_id = NULL)."""
    db.execute(
        delete(ExtractedFact).where(
            ExtractedFact.document_id == document_id, ExtractedFact.status.in_(("pendiente", "rechazado"))
        )
    )


def list_facts(
    db: Session, profile_id: str, document_id: str | None = None, statuses: list[str] | None = None
) -> list[ExtractedFact]:
    q = select(ExtractedFact).where(ExtractedFact.profile_id == profile_id)
    if document_id:
        q = q.where(ExtractedFact.document_id == document_id)
    if statuses:
        q = q.where(ExtractedFact.status.in_(statuses))
    return list(db.scalars(q.order_by(ExtractedFact.category, ExtractedFact.created_at, ExtractedFact.id)))
