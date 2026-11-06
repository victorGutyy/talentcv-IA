"""Tabla de tareas en segundo plano (persistida para sobrevivir a recargas de la interfaz)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

# Estados: en_cola -> ejecutando -> completado | error | cancelado | interrumpido
ACTIVE = ("en_cola", "ejecutando")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="en_cola")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(300), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
