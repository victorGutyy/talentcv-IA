"""Datos extraidos de documentos (o escritos por el usuario), siempre con su origen."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

# Estados: pendiente -> confirmado | editado | rechazado. Solo confirmado y editado se usan
# para generar el curriculum. Un dato escrito por el usuario (origin="manual") nace confirmado.
STATUSES = ("pendiente", "confirmado", "editado", "rechazado")
APPROVED = ("confirmado", "editado")


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    # Si se borra el documento, los datos aprobados se conservan sin documento; los demas se borran a mano.
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True, default=None
    )
    origin: Mapped[str] = mapped_column(String(10), default="documento")  # documento | manual
    category: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(
        JSON
    )  # solo campos verificados contra la cita, o lo escrito por el usuario
    original_data: Mapped[dict | None] = mapped_column(JSON, default=None)  # valor extraido antes de editarlo
    quote: Mapped[str] = mapped_column(Text, default="")  # fragmento literal del documento
    page: Mapped[int | None] = mapped_column(Integer, default=None)
    dropped_fields: Mapped[list] = mapped_column(JSON, default=list)  # campos descartados por no verificarse
    from_ocr: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # el texto vino de OCR: puede tener errores
    status: Mapped[str] = mapped_column(String(12), default="pendiente")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
