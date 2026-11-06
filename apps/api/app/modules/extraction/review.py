"""Revision humana de los datos: confirmar, editar, rechazar y agregar datos propios.

Regla central: solo lo `confirmado` o `editado` (o escrito por el usuario) se puede usar despues
para generar el curriculum. Lo que escribe el usuario no necesita cita: el usuario es la autoridad.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.extraction.models import APPROVED, ExtractedFact

TIPOS_CONTACTO = ("nombre", "email", "telefono", "ciudad", "pais", "enlace")
MAX_TEXTO = 300
MAX_LOGRO = 600
MAX_HABILIDADES = 40

# categoria -> (campos en orden, campos obligatorios)
CAMPOS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "contacto": (("tipo", "valor"), ("tipo", "valor")),
    "experiencia": (("cargo", "empresa", "inicio", "fin"), ("cargo",)),
    "educacion": (("titulo", "institucion", "fecha_graduacion"), ("titulo",)),
    "certificacion": (("nombre", "emisor", "fecha"), ("nombre",)),
    "idioma": (("idioma", "nivel"), ("idioma",)),
    "habilidad": (("nombres",), ("nombres",)),
    "logro": (("texto",), ("texto",)),
}
ACCIONES_LOTE = ("confirmar", "rechazar", "restaurar")


class FactNotFound(Exception):
    pass


class FactValidationError(ValueError):
    """`errors` asocia cada campo con un mensaje en espanol."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("datos no validos")
        self.errors = errors


def validar_datos(categoria: str, datos: dict) -> dict:
    if categoria not in CAMPOS:
        raise FactValidationError({"categoria": "Categoría desconocida."})
    campos, obligatorios = CAMPOS[categoria]
    errores: dict[str, str] = {}
    for extra in set(datos) - set(campos):
        errores[extra] = "Campo no permitido."

    limpio: dict = {}
    for campo in campos:
        valor = datos.get(campo)
        if campo == "nombres":
            items = valor if isinstance(valor, list) else []
            items = [i.strip() for i in items if isinstance(i, str) and i.strip()]
            if len(items) > MAX_HABILIDADES:
                errores[campo] = f"Máximo {MAX_HABILIDADES} habilidades."
            elif any(len(i) > 60 for i in items):
                errores[campo] = "Cada habilidad admite hasta 60 caracteres."
            limpio[campo] = items
            if not items and campo in obligatorios and campo not in errores:
                errores[campo] = "Escribe al menos una habilidad."
            continue
        if valor is not None and not isinstance(valor, str):
            errores[campo] = "Debe ser texto."
            limpio[campo] = None
            continue
        texto = (valor or "").strip() or None
        limite = MAX_LOGRO if campo == "texto" else MAX_TEXTO
        if texto and len(texto) > limite:
            errores[campo] = f"Máximo {limite} caracteres."
        if campo == "tipo" and texto and texto not in TIPOS_CONTACTO:
            errores[campo] = "Tipo de contacto no válido."
        if texto is None and campo in obligatorios and campo not in errores:
            errores[campo] = "Este campo es obligatorio."
        limpio[campo] = texto
    if errores:
        raise FactValidationError(errores)
    return limpio


def get_fact(db: Session, fact_id: str) -> ExtractedFact:
    fact = db.get(ExtractedFact, fact_id)
    if fact is None:
        raise FactNotFound(fact_id)
    return fact


def confirmar(fact: ExtractedFact) -> None:
    # Un dato ya editado sigue siendo "editado": conserva que el usuario lo corrigio.
    fact.status = "editado" if fact.status == "editado" else "confirmado"


def rechazar(fact: ExtractedFact) -> None:
    fact.status = "rechazado"


def restaurar(fact: ExtractedFact) -> None:
    fact.status = "pendiente"


def editar(fact: ExtractedFact, datos: dict) -> None:
    nuevos = validar_datos(fact.category, datos)
    if fact.origin == "documento":
        if fact.original_data is None:  # guardar solo el primer valor extraido
            fact.original_data = dict(fact.data)
        fact.status = "editado"
    else:  # un dato propio sigue siendo confirmado
        fact.status = "confirmado"
    fact.data = nuevos
    fact.dropped_fields = []  # el usuario ya revisó esos campos


def crear_manual(db: Session, profile_id: str, categoria: str, datos: dict) -> ExtractedFact:
    limpio = validar_datos(categoria, datos)
    fact = ExtractedFact(
        profile_id=profile_id,
        document_id=None,
        origin="manual",
        category=categoria,
        data=limpio,
        quote="",
        status="confirmado",
    )
    db.add(fact)
    db.commit()
    return fact


def aplicar_lote(db: Session, profile_id: str, ids: list[str], accion: str) -> dict:
    """Aplica la accion solo a datos de ESTE perfil. Los ids ajenos o inexistentes se ignoran."""
    operar = {"confirmar": confirmar, "rechazar": rechazar, "restaurar": restaurar}[accion]
    facts = list(
        db.scalars(
            select(ExtractedFact).where(ExtractedFact.profile_id == profile_id, ExtractedFact.id.in_(ids))
        )
    )
    for f in facts:
        operar(f)
    db.commit()
    return {"actualizados": len(facts), "ignorados": len(set(ids)) - len(facts)}


def aprobados(db: Session, profile_id: str) -> list[ExtractedFact]:
    return list(
        db.scalars(
            select(ExtractedFact)
            .where(ExtractedFact.profile_id == profile_id, ExtractedFact.status.in_(APPROVED))
            .order_by(ExtractedFact.category, ExtractedFact.created_at, ExtractedFact.id)
        )
    )
