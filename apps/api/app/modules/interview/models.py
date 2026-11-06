"""Preguntas del cuestionario que el usuario decidio omitir."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow


class InterviewSkip(Base):
    __tablename__ = "interview_skips"
    __table_args__ = (UniqueConstraint("profile_id", "question_id", name="uq_skip_profile_question"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(80))
    # True: el usuario respondio (la pregunta se cierra aunque queden campos en blanco).
    # False: la omitio; "volver a preguntar" solo reabre estas.
    answered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
