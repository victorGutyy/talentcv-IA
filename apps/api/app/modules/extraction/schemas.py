"""Esquema que el modelo debe devolver. Cada elemento lleva `cita`: el fragmento LITERAL del
documento que lo respalda. Sin cita verificable, el dato se descarta (ver evidence.py)."""

from typing import Literal

from pydantic import BaseModel


class DatoContacto(BaseModel):
    tipo: Literal["nombre", "email", "telefono", "ciudad", "pais", "enlace"]
    valor: str
    cita: str


class Experiencia(BaseModel):
    cargo: str
    empresa: str | None
    inicio: str | None
    fin: str | None
    cita: str


class Educacion(BaseModel):
    titulo: str
    institucion: str | None
    fecha_graduacion: str | None
    cita: str


class Certificacion(BaseModel):
    nombre: str
    emisor: str | None
    fecha: str | None
    cita: str


class Idioma(BaseModel):
    idioma: str
    nivel: str | None
    cita: str


class Habilidades(BaseModel):
    nombres: list[str]
    cita: str


class Logro(BaseModel):
    cita: str  # la frase literal del logro o responsabilidad


class ExtraccionCV(BaseModel):
    contacto: list[DatoContacto]
    experiencias: list[Experiencia]
    educacion: list[Educacion]
    certificaciones: list[Certificacion]
    idiomas: list[Idioma]
    habilidades: list[Habilidades]
    logros: list[Logro]


# categoria -> (lista en ExtraccionCV, campos que deben aparecer en la cita, campos obligatorios)
CATEGORIAS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "contacto": ("contacto", ("valor",), ("valor",)),
    "experiencia": ("experiencias", ("cargo", "empresa", "inicio", "fin"), ("cargo",)),
    "educacion": ("educacion", ("titulo", "institucion", "fecha_graduacion"), ("titulo",)),
    "certificacion": ("certificaciones", ("nombre", "emisor", "fecha"), ("nombre",)),
    "idioma": ("idiomas", ("idioma", "nivel"), ("idioma",)),
    "habilidad": ("habilidades", ("nombres",), ("nombres",)),
    "logro": ("logros", (), ()),
}

INSTRUCCIONES = """\
Analiza el currículum y extrae SOLO información que esté escrita en el documento.

Para cada elemento incluye `cita`: copia EXACTA y literal (sin cambiar ni una letra) la línea o
líneas del documento donde aparece el dato (máximo 300 caracteres). Todo valor que devuelvas
debe estar escrito dentro de su `cita`.

Reglas:
- Copia nombres, fechas y títulos tal como aparecen; no cambies el formato ni traduzcas.
- No deduzcas ni completes datos. Si un dato no aparece, usa null.
- Si no hay elementos de una categoría, devuelve una lista vacía.
- contacto: nombre, email, telefono, ciudad, pais o enlace (tipo y valor).
- experiencias: cargo, empresa, inicio, fin (usa el texto de la fecha, p. ej. «marzo 2021» o «actualidad»).
- educacion: titulo, institucion, fecha_graduacion.
- certificaciones: nombre, emisor, fecha.
- idiomas: idioma y nivel.
- habilidades: una entrada por línea o sección de habilidades, con la lista de nombres.
- logros: frases que describan resultados o responsabilidades laborales (solo la cita).
"""
