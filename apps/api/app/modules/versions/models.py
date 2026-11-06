"""Historial local de versiones: instantaneas inmutables del contenido del curriculum."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow


class CVVersion(Base):
    __tablename__ = "cv_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "content_hash", name="uq_version_contenido"),
        UniqueConstraint("profile_id", "numero", name="uq_version_numero"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)  # 1, 2, 3… por perfil
    etiqueta: Mapped[str | None] = mapped_column(String(80), default=None)
    origen: Mapped[str] = mapped_column(String(12))  # exportacion | manual
    content_hash: Mapped[str] = mapped_column(String(64))  # mismo contenido = misma version
    cv: Mapped[dict] = mapped_column(JSON)  # el CV exacto (ya saneado) de ese momento
    exportaciones: Mapped[list] = mapped_column(JSON, default=list)  # [{plantilla, formato, papel, fecha}]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
