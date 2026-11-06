"""Documentos importados por el usuario."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

# Estados: subido -> leido | error
PAGE_SEP = "\f"  # separador de paginas dentro de Document.text


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(80))  # nombre generado en disco
    kind: Mapped[str] = mapped_column(String(10))  # pdf | docx | image
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10), default="subido")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_pages: Mapped[list] = mapped_column(JSON, default=list)  # paginas leidas con OCR (base 1)
    text: Mapped[str] = mapped_column(Text, default="")  # paginas separadas por PAGE_SEP
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
