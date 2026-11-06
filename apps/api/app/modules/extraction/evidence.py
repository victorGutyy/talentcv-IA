"""Verificacion de evidencia: ningun dato del modelo pasa si no esta escrito en el documento.

Reglas:
1. La `cita` debe aparecer literalmente (normalizada) en el documento; asi se obtiene su pagina.
2. Cada valor de campo debe aparecer dentro de su cita. Si no, el campo se descarta.
3. Si falla un campo obligatorio, se descarta todo el elemento.
Normalizar = minusculas, sin acentos, solo letras y digitos (el OCR y el formato varian).
"""

import bisect
import re
import unicodedata
from dataclasses import dataclass, field

MIN_QUOTE = 6  # caracteres normalizados; evita citas triviales como «2020»
MAX_QUOTE = 600


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^0-9a-z]+", " ", text.casefold())
    return text.strip()


class DocumentIndex:
    """Texto normalizado del documento, con el mapa a su numero de pagina."""

    def __init__(self, pages: list[str]):
        parts: list[str] = []
        self._starts: list[int] = []
        pos = 0
        for p in pages:
            n = normalize(p)
            self._starts.append(pos)
            parts.append(n)
            pos += len(n) + 1
        self.text = " ".join(parts)

    def find_page(self, quote: str) -> int | None:
        """Pagina (base 1) donde empieza la cita, o None si no esta en el documento."""
        q = normalize(quote)
        if len(q) < MIN_QUOTE or len(q) > MAX_QUOTE:
            return None
        i = self.text.find(q)
        if i < 0:
            return None
        return bisect.bisect_right(self._starts, i)  # base 1


@dataclass
class Verified:
    category: str
    data: dict
    quote: str
    page: int
    dropped_fields: list[str] = field(default_factory=list)


@dataclass
class Rejected:
    category: str
    reason: str  # cita_no_encontrada | campo_obligatorio_sin_respaldo
    detail: str = ""


def _in_quote(value: str, quote_norm: str) -> bool:
    v = normalize(value)
    return bool(v) and v in quote_norm


def verify_item(
    category: str,
    item: dict,
    quote_fields: tuple[str, ...],
    required: tuple[str, ...],
    index: DocumentIndex,
) -> Verified | Rejected:
    quote = (item.get("cita") or "").strip()
    page = index.find_page(quote)
    if page is None:
        return Rejected(category, "cita_no_encontrada", quote[:80])

    q_norm = normalize(quote)
    data: dict = {}
    dropped: list[str] = []
    for name in quote_fields:
        value = item.get(name)
        if value is None:
            data[name] = None
        elif isinstance(value, list):  # p. ej. habilidades: se conserva solo lo respaldado
            ok = [v for v in value if isinstance(v, str) and _in_quote(v, q_norm)]
            if len(ok) < len(value):
                dropped.append(name)
            data[name] = ok
        elif isinstance(value, str) and _in_quote(value, q_norm):
            data[name] = value.strip()
        else:
            data[name] = None
            dropped.append(name)

    for name in required:
        if not data.get(name):
            return Rejected(category, "campo_obligatorio_sin_respaldo", name)

    if category == "contacto":
        data["tipo"] = item.get("tipo")
    if category == "logro":
        data["texto"] = quote
    return Verified(category, data, quote, page, dropped)


def fingerprint(category: str, data: dict) -> str:
    """Clave para detectar duplicados entre fragmentos o ejecuciones."""
    parts = []
    for k in sorted(data):
        v = data[k]
        parts.append(f"{k}={normalize(' '.join(v)) if isinstance(v, list) else normalize(str(v or ''))}")
    return category + "|" + "|".join(parts)
