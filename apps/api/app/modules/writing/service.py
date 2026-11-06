"""Logica de redaccion: material aprobado, borradores y su aprobacion. No conoce HTTP ni la IA."""

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.extraction import review
from app.modules.extraction.evidence import normalize
from app.modules.extraction.models import ExtractedFact
from app.modules.profiles.models import Profile
from app.modules.writing import audit
from app.modules.writing.models import Draft
from app.modules.writing.prompts import MAX_PUNTO, MAX_RESUMEN

MAX_CHARS = {"resumen": MAX_RESUMEN, "logro": MAX_PUNTO}


class DraftNotFound(Exception):
    pass


class DraftBlocked(Exception):
    """El borrador de la IA no paso la auditoria: no puede aprobarse tal cual."""


class DraftInvalid(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("borrador no valido")
        self.errors = errors


# ----------------------------------------------------------------- material aprobado
@dataclass
class Material:
    perfil: Profile
    por_cat: dict[str, list[ExtractedFact]]

    @property
    def hay_datos(self) -> bool:
        return any(self.por_cat.values())

    @property
    def experiencias(self) -> list[ExtractedFact]:
        return self.por_cat.get("experiencia", [])


def cargar(db: Session, profile_id: str) -> Material:
    perfil = db.get(Profile, profile_id)
    por_cat: dict[str, list[ExtractedFact]] = {}
    for f in review.aprobados(db, profile_id):
        por_cat.setdefault(f.category, []).append(f)
    return Material(perfil, por_cat)


def _valores(data: dict) -> list[str]:
    out: list[str] = []
    for k, v in data.items():
        if k == "tipo":
            continue
        if isinstance(v, list):
            out += [str(x) for x in v if x]
        elif v:
            out.append(str(v))
    return out


def fuentes_resumen(m: Material) -> list[str]:
    """Todo lo que el resumen puede mencionar: perfil + datos aprobados (nunca la oferta)."""
    p = m.perfil
    textos = [p.nombre_completo, p.titular or "", p.ciudad or "", p.pais or "", p.resumen or ""]
    for hechos in m.por_cat.values():
        for f in hechos:
            textos += _valores(f.data)
    return [t for t in textos if t]


def bloque_datos(m: Material) -> str:
    """Datos del perfil en lineas simples, para entregarlos al modelo."""
    p = m.perfil
    L: list[str] = []
    if p.titular:
        L.append(f"TITULAR: {p.titular}")
    ubic = ", ".join(x for x in (p.ciudad, p.pais) if x)
    if ubic:
        L.append(f"UBICACIÓN: {ubic}")
    for f in m.por_cat.get("experiencia", []):
        d = f.data
        fechas = " – ".join(x for x in (d.get("inicio"), d.get("fin")) if x)
        L.append(f"EXPERIENCIA: {review.etiqueta_experiencia(f)}" + (f" ({fechas})" if fechas else ""))
    for f in m.por_cat.get("educacion", []):
        d = f.data
        L.append(
            "ESTUDIOS: "
            + ", ".join(
                str(x) for x in (d.get("titulo"), d.get("institucion"), d.get("fecha_graduacion")) if x
            )
        )
    for f in m.por_cat.get("habilidad", []):
        L.append("HABILIDADES: " + ", ".join(f.data.get("nombres") or []))
    for f in m.por_cat.get("idioma", []):
        L.append("IDIOMA: " + ", ".join(str(x) for x in (f.data.get("idioma"), f.data.get("nivel")) if x))
    for f in m.por_cat.get("certificacion", []):
        d = f.data
        L.append(
            "CERTIFICACIÓN: "
            + ", ".join(str(x) for x in (d.get("nombre"), d.get("emisor"), d.get("fecha")) if x)
        )
    for f in m.por_cat.get("logro", []):
        L.append(f"LOGRO: {f.data.get('texto')}")
    if p.resumen:
        L.append(f"RESUMEN ESCRITO POR LA PERSONA: {p.resumen}")
    return "\n".join(L)


def puntos(m: Material) -> list[tuple[ExtractedFact, ExtractedFact]]:
    """(puesto, logro) para cada logro aprobado ligado a un puesto aprobado."""
    out = []
    for exp in m.experiencias:
        clave = normalize(review.etiqueta_experiencia(exp))
        for lg in m.por_cat.get("logro", []):
            if normalize(str(lg.data.get("contexto") or "")) == clave:
                out.append((exp, lg))
    return out


def logros_sin_puesto(m: Material) -> list[ExtractedFact]:
    claves = {normalize(review.etiqueta_experiencia(e)) for e in m.experiencias}
    return [
        lg for lg in m.por_cat.get("logro", []) if normalize(str(lg.data.get("contexto") or "")) not in claves
    ]


def fuentes_punto(exp: ExtractedFact, logro: ExtractedFact) -> list[str]:
    d = exp.data
    return [
        str(logro.data.get("texto") or ""),
        *[str(d.get(k)) for k in ("cargo", "empresa", "inicio", "fin") if d.get(k)],
    ]


# ----------------------------------------------------------------- borradores
def listar(db: Session, profile_id: str) -> list[Draft]:
    return list(
        db.scalars(
            select(Draft)
            .where(Draft.profile_id == profile_id)
            .order_by(Draft.section.desc(), Draft.created_at, Draft.id)
        )
    )


def get(db: Session, draft_id: str) -> Draft:
    d = db.get(Draft, draft_id)
    if d is None:
        raise DraftNotFound(draft_id)
    return d


def limpiar_ia_no_aprobada(db: Session, profile_id: str) -> None:
    """Al regenerar se descartan los borradores de la IA no aprobados; lo aprobado y lo del usuario se conserva."""
    db.execute(
        delete(Draft).where(Draft.profile_id == profile_id, Draft.origin == "ia", Draft.status != "aprobado")
    )
    db.commit()


def tiene_aprobado(db: Session, profile_id: str, section: str, source_id: str | None = None) -> bool:
    for d in db.scalars(
        select(Draft).where(
            Draft.profile_id == profile_id, Draft.section == section, Draft.status == "aprobado"
        )
    ):
        if source_id is None or source_id in d.source_ids:
            return True
    return False


def guardar(
    db: Session,
    profile_id: str,
    section: str,
    texto: str,
    resultado: audit.AuditResult,
    *,
    target_fact_id: str | None = None,
    source_ids: list[str] | None = None,
) -> Draft:
    d = Draft(
        profile_id=profile_id,
        section=section,
        target_fact_id=target_fact_id,
        source_ids=source_ids or [],
        text=texto.strip(),
        origin="ia",
        audit_ok=resultado.ok,
        audit_issues=[i.as_dict() for i in resultado.issues],
        audit_warnings=resultado.warnings,
    )
    db.add(d)
    db.commit()
    return d


def _fuentes_de(db: Session, d: Draft) -> list[str]:
    m = cargar(db, d.profile_id)
    if d.section == "resumen":
        return fuentes_resumen(m)
    exp = db.get(ExtractedFact, d.target_fact_id) if d.target_fact_id else None
    logro = db.get(ExtractedFact, d.source_ids[0]) if d.source_ids else None
    return fuentes_punto(exp, logro) if exp and logro else []


def _aplicar_auditoria(db: Session, d: Draft) -> None:
    r = audit.auditar(d.text, _fuentes_de(db, d), max_chars=MAX_CHARS[d.section])
    d.audit_ok, d.audit_issues, d.audit_warnings = r.ok, [i.as_dict() for i in r.issues], r.warnings


def actuar(db: Session, d: Draft, accion: str, texto: str | None = None) -> None:
    if accion == "editar":
        nuevo = (texto or "").strip()
        if not nuevo:
            raise DraftInvalid({"texto": "El texto no puede estar vacío."})
        if len(nuevo) > MAX_CHARS[d.section]:
            raise DraftInvalid({"texto": f"Máximo {MAX_CHARS[d.section]} caracteres."})
        d.text, d.origin, d.status = nuevo, "usuario", "borrador"
        _aplicar_auditoria(db, d)  # solo informa: el texto es del usuario
    elif accion == "aprobar":
        if d.origin == "ia" and not d.audit_ok:
            raise DraftBlocked(d.id)
        d.status = "aprobado"
    elif accion == "rechazar":
        d.status = "rechazado"
    elif accion == "restaurar":
        d.status = "borrador"
    db.commit()
