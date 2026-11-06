"""Datos extraidos de documentos, siempre con su fuente."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

CATEGORIES = ("contacto", "experiencia", "educacion", "certificacion", "idioma")
# pendiente -> confirmado | editado | rechazado  (la confirmacion llega en la Fase 4)


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON)  # solo campos verificados contra la cita
    quote: Mapped[str] = mapped_column(Text)  # fragmento literal del documento
    page: Mapped[int | None] = mapped_column(Integer, default=None)
    dropped_fields: Mapped[list] = mapped_column(JSON, default=list)  # campos descartados por no verificarse
    from_ocr: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # el texto vino de OCR: puede tener errores
    status: Mapped[str] = mapped_column(String(12), default="pendiente")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
