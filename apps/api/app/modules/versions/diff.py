"""Comparacion de dos versiones del curriculum, seccion por seccion y linea por linea."""

from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

from app.modules.export.cv import CV


class Cambio(BaseModel):
    seccion: str
    tipo: Literal["agregado", "quitado", "cambiado"]
    antes: str | None = None
    despues: str | None = None


def lineas(cv: CV) -> dict[str, list[str]]:
    """El curriculum como listas de lineas de texto, por seccion (el orden de las secciones es fijo)."""
    c = cv.contacto
    out: dict[str, list[str]] = {
        "Cabecera": [x for x in (cv.nombre, cv.titular, c.email, c.telefono, c.ubicacion, *c.enlaces) if x],
        "Resumen": [cv.resumen] if cv.resumen else [],
        "Experiencia": [],
        "Educación": [
            " — ".join(x for x in (e.titulo, e.institucion) if x) + (f" ({e.fecha})" if e.fecha else "")
            for e in cv.educacion
        ],
        "Habilidades": list(cv.habilidades),
        "Idiomas": list(cv.idiomas),
        "Certificaciones": [
            " — ".join(x for x in (k.nombre, k.emisor) if x) + (f" ({k.fecha})" if k.fecha else "")
            for k in cv.certificaciones
        ],
        "Logros destacados": list(cv.logros),
    }
    for p in cv.experiencia:
        cab = " — ".join(x for x in (p.cargo, p.empresa) if x) + (f" ({p.fechas})" if p.fechas else "")
        out["Experiencia"] += [cab, *[f"• {x}" for x in p.puntos]]
    return out


def comparar(a: CV, b: CV) -> list[Cambio]:
    """Cambios para pasar de `a` (antes) a `b` (despues)."""
    la, lb = lineas(a), lineas(b)
    cambios: list[Cambio] = []
    for seccion in la:
        x, y = la[seccion], lb[seccion]
        for op, i1, i2, j1, j2 in SequenceMatcher(a=x, b=y, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            antes, despues = x[i1:i2], y[j1:j2]
            pares = min(len(antes), len(despues)) if op == "replace" else 0
            for k in range(pares):
                cambios.append(Cambio(seccion=seccion, tipo="cambiado", antes=antes[k], despues=despues[k]))
            cambios += [Cambio(seccion=seccion, tipo="quitado", antes=t) for t in antes[pares:]]
            cambios += [Cambio(seccion=seccion, tipo="agregado", despues=t) for t in despues[pares:]]
    return cambios
