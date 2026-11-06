"""Esquemas de entrada/salida de perfiles, con validacion estricta."""

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_TEL = re.compile(r"^[0-9+()\-.\s]{5,40}$")


def _limpiar(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class Enlace(BaseModel):
    etiqueta: str = Field(min_length=1, max_length=60)
    url: str = Field(max_length=500)

    @field_validator("etiqueta")
    @classmethod
    def _etiqueta(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La etiqueta no puede estar vacía")
        return v

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        p = urlparse(v)
        if p.scheme not in ("http", "https") or not p.netloc:
            raise ValueError("La URL debe comenzar con http:// o https://")
        return v


class ProfileIn(BaseModel):
    """Datos que el usuario escribe. Nada aqui proviene de la IA."""

    nombre_completo: str = Field(max_length=200)
    titular: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    telefono: str | None = Field(default=None, max_length=40)
    ciudad: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    enlaces: list[Enlace] = Field(default_factory=list, max_length=10)
    resumen: str | None = Field(default=None, max_length=2000)

    @field_validator("nombre_completo")
    @classmethod
    def _nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre completo es obligatorio")
        return v

    @field_validator("titular", "ciudad", "pais", "resumen")
    @classmethod
    def _opcionales(cls, v: str | None) -> str | None:
        return _limpiar(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        v = _limpiar(v)
        if v is not None and not _EMAIL.match(v):
            raise ValueError("El correo electrónico no es válido")
        return v

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, v: str | None) -> str | None:
        v = _limpiar(v)
        if v is not None and not _TEL.match(v):
            raise ValueError("El teléfono solo puede contener dígitos, espacios y + ( ) - .")
        return v


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    creado_en: datetime
    actualizado_en: datetime


class ProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre_completo: str
    titular: str | None
    actualizado_en: datetime
