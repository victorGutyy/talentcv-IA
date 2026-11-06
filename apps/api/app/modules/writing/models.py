"""Borradores de texto redactados (por la IA o por el usuario) a partir de datos aprobados."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

# seccion: "resumen" (uno por perfil) | "logro" (un punto de un puesto)
# estado: borrador -> aprobado | rechazado. Solo lo aprobado pasa al curriculum.


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(10))
    # Puesto (hecho de experiencia) al que pertenece un punto; None para el resumen.
    target_fact_id: Mapped[str | None] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"), index=True, default=None
    )
    source_ids: Mapped[list] = mapped_column(JSON, default=list)  # hechos de los que sale el texto
    text: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(10), default="ia")  # ia | usuario
    status: Mapped[str] = mapped_column(String(10), default="borrador")
    audit_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    audit_issues: Mapped[list] = mapped_column(JSON, default=list)  # [{tipo, detalle}] que bloquean
    audit_warnings: Mapped[list] = mapped_column(JSON, default=list)  # avisos que solo informan
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
