"""Entrevistador: detecta que falta en la informacion APROBADA y pregunta de a una cosa.

Es determinista (reglas, sin IA): rapido en CPU, repetible y facil de probar. Las respuestas son
del propio usuario, asi que se guardan como datos aprobados.
Solo se preguntan huecos de datos aprobados; lo pendiente de revisar no cuenta (primero se revisa).
"""

from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.extraction import review
from app.modules.extraction.evidence import normalize
from app.modules.extraction.models import ExtractedFact
from app.modules.interview.models import InterviewSkip
from app.modules.profiles import service as profiles
from app.modules.profiles.models import Profile
from app.modules.profiles.schemas import ProfileIn

MAX_LOGROS = 5


class CampoPregunta(BaseModel):
    key: str
    label: str
    tipo: Literal["texto", "area", "lista", "select"] = "texto"
    obligatorio: bool = False
    ayuda: str | None = None
    opciones: list[tuple[str, str]] | None = None  # (valor, etiqueta) para select


class Pregunta(BaseModel):
    id: str
    tipo: Literal["perfil", "campos", "nuevo", "logro"]
    categoria: str | None = None
    texto: str
    ayuda: str | None = None
    contexto: str | None = None
    opcional: bool = False
    campos: list[CampoPregunta]
    prioridad: int = 50


class EstadoEntrevista(BaseModel):
    siguiente: Pregunta | None
    restantes: int
    omitidas: int
    pendientes_de_revision: int


class QuestionGone(Exception):
    """La pregunta ya no aplica (se respondio o el dato cambio)."""


# ----------------------------------------------------------------- campos reutilizables
def _c(key, label, tipo="texto", obligatorio=False, ayuda=None) -> CampoPregunta:
    return CampoPregunta(key=key, label=label, tipo=tipo, obligatorio=obligatorio, ayuda=ayuda)


CAMPOS_EXPERIENCIA = {
    "cargo": _c("cargo", "Cargo", obligatorio=True),
    "empresa": _c("empresa", "Empresa"),
    "inicio": _c("inicio", "¿Cuándo empezaste?", ayuda="Por ejemplo: marzo 2020"),
    "fin": _c("fin", "¿Cuándo terminaste?", ayuda="Escribe «actualidad» si sigues en el puesto"),
}
CAMPOS_EDUCACION = {
    "titulo": _c("titulo", "Título o programa", obligatorio=True),
    "institucion": _c("institucion", "Institución"),
    "fecha_graduacion": _c(
        "fecha_graduacion", "¿Cuándo terminaste?", ayuda="Año o fecha. Escribe «en curso» si aún estudias"
    ),
}


def _label_experiencia(f: ExtractedFact) -> str:
    cargo, empresa = f.data.get("cargo"), f.data.get("empresa")
    return f"{cargo} – {empresa}" if empresa else str(cargo)


def _faltan(f: ExtractedFact, campos: tuple[str, ...]) -> list[str]:
    return [c for c in campos if not f.data.get(c)]


# ----------------------------------------------------------------- reglas de huecos
def construir_preguntas(db: Session, profile_id: str) -> list[Pregunta]:
    """Todas las preguntas abiertas (sin las omitidas), ordenadas por importancia."""
    perfil = db.get(Profile, profile_id)
    aprobados = review.aprobados(db, profile_id)
    por_cat: dict[str, list[ExtractedFact]] = {}
    for f in aprobados:
        por_cat.setdefault(f.category, []).append(f)
    omitidas = set(
        db.scalars(select(InterviewSkip.question_id).where(InterviewSkip.profile_id == profile_id))
    )

    contacto = por_cat.get("contacto", [])

    def hay_contacto(*tipos: str) -> bool:
        return any(f.data.get("tipo") in tipos and f.data.get("valor") for f in contacto)

    qs: list[Pregunta] = []

    def add(**kw) -> None:
        qs.append(Pregunta(**kw))

    # 1) contacto y presentacion (perfil)
    if not perfil.email and not hay_contacto("email"):
        add(
            id="perfil:email",
            tipo="perfil",
            categoria="contacto",
            prioridad=10,
            texto="¿Cuál es tu correo electrónico de contacto?",
            ayuda="Aparecerá en la cabecera de tu currículum.",
            campos=[_c("email", "Correo electrónico", obligatorio=True)],
        )
    if not perfil.telefono and not hay_contacto("telefono"):
        add(
            id="perfil:telefono",
            tipo="perfil",
            categoria="contacto",
            prioridad=11,
            opcional=True,
            texto="¿Qué teléfono quieres mostrar?",
            campos=[
                _c("telefono", "Teléfono", obligatorio=True, ayuda="Con indicativo, p. ej. +57 300 000 0000")
            ],
        )
    if not (perfil.ciudad or perfil.pais) and not hay_contacto("ciudad", "pais"):
        add(
            id="perfil:ubicacion",
            tipo="perfil",
            categoria="contacto",
            prioridad=12,
            opcional=True,
            texto="¿Dónde vives?",
            ayuda="Basta con la ciudad o el país.",
            campos=[_c("ciudad", "Ciudad"), _c("pais", "País")],
        )
    if not perfil.titular:
        add(
            id="perfil:titular",
            tipo="perfil",
            categoria="perfil",
            prioridad=20,
            texto="¿Cómo te presentas profesionalmente?",
            ayuda="Una línea bajo tu nombre, p. ej. «Ingeniera de sistemas» o «Analista de datos».",
            campos=[_c("titular", "Titular profesional", obligatorio=True)],
        )

    # 2) experiencia
    experiencias = por_cat.get("experiencia", [])
    if not experiencias:
        add(
            id="nuevo:experiencia",
            tipo="nuevo",
            categoria="experiencia",
            prioridad=30,
            texto="¿Cuál ha sido tu experiencia laboral más reciente?",
            ayuda="Agrega un puesto. Podrás añadir más desde «Revisar datos».",
            campos=[CAMPOS_EXPERIENCIA[k] for k in ("cargo", "empresa", "inicio", "fin")],
        )
    for f in experiencias:
        etiqueta = _label_experiencia(f)
        faltan = _faltan(f, ("empresa", "inicio", "fin"))
        if faltan:
            add(
                id=f"campos:{f.id}",
                tipo="campos",
                categoria="experiencia",
                prioridad=31,
                contexto=etiqueta,
                texto=f"Completa los datos de tu puesto de {f.data.get('cargo')}.",
                ayuda="Deja en blanco lo que no quieras indicar.",
                campos=[CAMPOS_EXPERIENCIA[k] for k in faltan],
            )
        tiene_logros = any(
            normalize(str(lg.data.get("contexto") or "")) == normalize(etiqueta)
            for lg in por_cat.get("logro", [])
        )
        if not tiene_logros:
            add(
                id=f"logro:{f.id}",
                tipo="logro",
                categoria="logro",
                prioridad=50,
                opcional=True,
                contexto=etiqueta,
                texto=f"¿Qué lograste como {f.data.get('cargo')}?",
                ayuda="Resultados concretos, con números si puedes. Escribe uno por línea (máximo 5).",
                campos=[_c("texto", "Logros", tipo="area", obligatorio=True)],
            )

    # 3) educacion
    educacion = por_cat.get("educacion", [])
    if not educacion:
        add(
            id="nuevo:educacion",
            tipo="nuevo",
            categoria="educacion",
            prioridad=40,
            opcional=True,
            texto="¿Qué estudios has realizado?",
            ayuda="Agrega el más importante.",
            campos=[CAMPOS_EDUCACION[k] for k in ("titulo", "institucion", "fecha_graduacion")],
        )
    for f in educacion:
        faltan = _faltan(f, ("institucion", "fecha_graduacion"))
        if faltan:
            add(
                id=f"campos:{f.id}",
                tipo="campos",
                categoria="educacion",
                prioridad=41,
                contexto=str(f.data.get("titulo")),
                texto=f"Completa los datos de «{f.data.get('titulo')}».",
                ayuda="Solo escribe lo que sepas con certeza.",
                campos=[CAMPOS_EDUCACION[k] for k in faltan],
            )

    # 4) resumen, habilidades, idiomas, certificaciones
    if not perfil.resumen:
        add(
            id="perfil:resumen",
            tipo="perfil",
            categoria="perfil",
            prioridad=55,
            texto="Cuéntame en dos o tres frases quién eres profesionalmente.",
            ayuda="Es tu texto: en la fase de redacción te ayudaré a pulirlo sin cambiar los hechos.",
            campos=[_c("resumen", "Resumen", tipo="area", obligatorio=True)],
        )
    if not por_cat.get("habilidad"):
        add(
            id="nuevo:habilidad",
            tipo="nuevo",
            categoria="habilidad",
            prioridad=70,
            texto="¿Qué habilidades quieres destacar?",
            ayuda="Herramientas, tecnologías o competencias.",
            campos=[
                _c("nombres", "Habilidades", tipo="lista", obligatorio=True, ayuda="Sepáralas con comas")
            ],
        )
    idiomas = por_cat.get("idioma", [])
    if not idiomas:
        add(
            id="nuevo:idioma",
            tipo="nuevo",
            categoria="idioma",
            prioridad=80,
            opcional=True,
            texto="¿Qué idiomas hablas?",
            ayuda="Agrega uno; podrás añadir más después.",
            campos=[
                _c("idioma", "Idioma", obligatorio=True),
                _c("nivel", "Nivel", ayuda="Por ejemplo: nativo, B2"),
            ],
        )
    for f in idiomas:
        if not f.data.get("nivel"):
            add(
                id=f"campos:{f.id}",
                tipo="campos",
                categoria="idioma",
                prioridad=81,
                opcional=True,
                contexto=str(f.data.get("idioma")),
                texto=f"¿Qué nivel tienes de {f.data.get('idioma')}?",
                campos=[_c("nivel", "Nivel", obligatorio=True, ayuda="Por ejemplo: nativo, intermedio, B2")],
            )
    for f in por_cat.get("certificacion", []):
        faltan = _faltan(f, ("emisor", "fecha"))
        if faltan:
            nombres = {"emisor": _c("emisor", "Entidad emisora"), "fecha": _c("fecha", "Fecha")}
            add(
                id=f"campos:{f.id}",
                tipo="campos",
                categoria="certificacion",
                prioridad=90,
                opcional=True,
                contexto=str(f.data.get("nombre")),
                texto=f"Completa los datos de la certificación «{f.data.get('nombre')}».",
                campos=[nombres[k] for k in faltan],
            )

    abiertas = [q for q in qs if q.id not in omitidas]
    return sorted(abiertas, key=lambda q: q.prioridad)  # sorted es estable: conserva el orden de creacion


def estado(db: Session, profile_id: str) -> EstadoEntrevista:
    preguntas = construir_preguntas(db, profile_id)
    omitidas = db.scalar(
        select(func.count())
        .select_from(InterviewSkip)
        .where(InterviewSkip.profile_id == profile_id, InterviewSkip.answered.is_(False))
    )
    pendientes = db.scalar(
        select(func.count())
        .select_from(ExtractedFact)
        .where(ExtractedFact.profile_id == profile_id, ExtractedFact.status == "pendiente")
    )
    return EstadoEntrevista(
        siguiente=preguntas[0] if preguntas else None,
        restantes=len(preguntas),
        omitidas=omitidas or 0,
        pendientes_de_revision=pendientes or 0,
    )


# ----------------------------------------------------------------- acciones
def _abierta(db: Session, profile_id: str, question_id: str) -> Pregunta:
    for q in construir_preguntas(db, profile_id):
        if q.id == question_id:
            return q
    raise QuestionGone(question_id)


def _limpiar(valores: dict, q: Pregunta) -> dict[str, str]:
    extra = set(valores) - {c.key for c in q.campos}
    if extra:
        raise review.FactValidationError({k: "Campo no permitido." for k in extra})
    limpio = {k: v.strip() for k, v in valores.items() if isinstance(v, str) and v.strip()}
    if not limpio:
        raise review.FactValidationError({"__": "Escribe al menos una respuesta o usa «Omitir»."})
    return limpio


def _guardar_perfil(db: Session, profile_id: str, cambios: dict[str, str]) -> None:
    perfil = db.get(Profile, profile_id)
    actual = ProfileIn.model_validate(perfil, from_attributes=True).model_dump()
    try:
        nuevo = ProfileIn.model_validate({**actual, **cambios})
    except ValidationError as e:
        errores = {str(x["loc"][0]): str(x["msg"]).replace("Value error, ", "") for x in e.errors()}
        raise review.FactValidationError(errores) from None
    profiles.actualizar(db, profile_id, nuevo)


def responder(db: Session, profile_id: str, question_id: str, valores: dict) -> None:
    q = _abierta(db, profile_id, question_id)
    datos = _limpiar(valores, q)

    if q.tipo == "perfil":
        _guardar_perfil(db, profile_id, datos)
    elif q.tipo == "nuevo":
        review.crear_manual(db, profile_id, q.categoria or "", datos | _lista(datos))
    elif q.tipo == "campos":
        fact = review.get_fact(db, question_id.split(":", 1)[1])
        review.editar(fact, {**fact.data, **datos})
        db.commit()
        # Pregunta cerrada: no se insiste con lo que quedo en blanco (pero no cuenta como omitida).
        _cerrar(db, profile_id, question_id, respondida=True)
    elif q.tipo == "logro":
        lineas = [ln.strip() for ln in datos["texto"].splitlines() if ln.strip()][:MAX_LOGROS]
        for linea in lineas:
            review.crear_manual(db, profile_id, "logro", {"texto": linea, "contexto": q.contexto})


def _lista(datos: dict[str, str]) -> dict:
    """Los campos de tipo lista llegan como texto separado por comas."""
    if "nombres" in datos:
        return {"nombres": [x.strip() for x in datos["nombres"].replace("\n", ",").split(",") if x.strip()]}
    return {}


def _cerrar(db: Session, profile_id: str, question_id: str, *, respondida: bool) -> None:
    ya = db.scalar(
        select(InterviewSkip.id).where(
            InterviewSkip.profile_id == profile_id, InterviewSkip.question_id == question_id
        )
    )
    if not ya:
        db.add(InterviewSkip(profile_id=profile_id, question_id=question_id, answered=respondida))
        db.commit()


def omitir(db: Session, profile_id: str, question_id: str) -> None:
    _abierta(db, profile_id, question_id)
    _cerrar(db, profile_id, question_id, respondida=False)


def reiniciar(db: Session, profile_id: str) -> None:
    """Reabre solo lo omitido; lo que el usuario ya respondio no se vuelve a preguntar."""
    db.execute(
        delete(InterviewSkip).where(InterviewSkip.profile_id == profile_id, InterviewSkip.answered.is_(False))
    )
    db.commit()
