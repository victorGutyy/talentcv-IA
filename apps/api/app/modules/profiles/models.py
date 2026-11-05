"""Modelo de datos de perfiles personales."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    nombre_completo: Mapped[str] = mapped_column(String(200))
    titular: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    telefono: Mapped[str | None] = mapped_column(String(40), default=None)
    ciudad: Mapped[str | None] = mapped_column(String(120), default=None)
    pais: Mapped[str | None] = mapped_column(String(120), default=None)
    enlaces: Mapped[list] = mapped_column(JSON, default=list)
    resumen: Mapped[str | None] = mapped_column(Text, default=None)
    creado_en: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
