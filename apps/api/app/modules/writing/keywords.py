"""Optimizador de palabras clave: compara una oferta con la informacion APROBADA del perfil.

Es determinista. No agrega nada al curriculum: solo indica que terminos de la oferta aparecen en tus
datos y cuales no, para que decidas si tienes esa experiencia (y la agregues) o no la menciones.
"""

import re
from collections import Counter
from collections.abc import Iterable

from app.modules.extraction.evidence import normalize

MAX_OFERTA = 6000
MAX_TERMINOS = 25

STOPWORDS = frozenset(
    """para como entre sobre desde hasta durante mediante cuando donde tambien ademas cada otros otras este
    esta estos estas esos esas ellos ellas tiene tener tienen tuvo siendo sido sera seran fueron habia dentro
    fuera mismo misma ser estar contar buscamos busca buscando requisitos requerimientos requerido requeridos
    requerida experiencia anos ano minimo minima deseable deseables ofrecemos ofrece oferta puesto cargo
    vacante empresa equipo trabajo trabajar capacidad habilidad habilidades conocimiento conocimientos
    manejo nivel avanzado intermedio basico excelente buena bueno buen buenas buenos persona personas
    responsabilidades funciones perfil formacion profesional profesionales area areas tipo tareas tarea
    proceso procesos desarrollo desarrollar apoyo ademas segun cualquier nuestro nuestra nuestros nuestras
    sera ademas junto bajo hacia tanto tantos muy mas menos todo toda todos todas otro otra sin con por una
    los las del que sus son han hay requiere requieren requerimos requiero valora valoran valorara
    incorporamos incorporar buscamos importante deseamos necesitamos necesario""".split()
)


def terminos_de_oferta(oferta: str) -> list[str]:
    """Terminos relevantes de la oferta (en su forma original), por frecuencia y orden de aparicion."""
    oferta = oferta[:MAX_OFERTA]
    originales: dict[str, str] = {}
    cuenta: Counter[str] = Counter()
    for m in re.finditer(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ+#.]*", oferta):
        palabra = m.group(0).strip(".")
        n = normalize(palabra)
        if len(n) < 3 or " " in n or n in STOPWORDS or n.isdigit():
            continue
        cuenta[n] += 1
        originales.setdefault(n, palabra)
    orden = {n: i for i, n in enumerate(originales)}
    ranking = sorted(cuenta, key=lambda n: (-cuenta[n], orden[n]))
    return [originales[n] for n in ranking[:MAX_TERMINOS]]


def comparar(oferta: str, fuentes: Iterable[str]) -> dict[str, list[str]]:
    """Separa los terminos de la oferta en los que aparecen en tus datos aprobados y los que no."""
    src = set(normalize(" ".join(fuentes)).split())
    coinciden, faltan = [], []
    for t in terminos_de_oferta(oferta):
        (coinciden if normalize(t) in src else faltan).append(t)
    return {"coinciden": coinciden, "faltan": faltan}
