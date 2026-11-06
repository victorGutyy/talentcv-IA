"""Modelo del curriculum: se arma SOLO con informacion aprobada por el usuario.

Entra: datos confirmados/editados/propios, textos redactados APROBADOS, y los campos que el propio
usuario escribio en su perfil. Nunca entra: datos pendientes o rechazados, ni borradores sin aprobar.
"""

import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.extraction import review
from app.modules.extraction.evidence import normalize
from app.modules.extraction.models import ExtractedFact
from app.modules.profiles.models import Profile
from app.modules.writing.models import Draft

ACTUAL = {"actualidad", "presente", "actual", "hoy", "la fecha"}


class Contacto(BaseModel):
    email: str | None = None
    telefono: str | None = None
    ubicacion: str | None = None
    enlaces: list[str] = []


class Puesto(BaseModel):
    cargo: str
    empresa: str | None = None
    fechas: str | None = None
    puntos: list[str] = []


class Estudio(BaseModel):
    titulo: str
    institucion: str | None = None
    fecha: str | None = None


class Certificacion(BaseModel):
    nombre: str
    emisor: str | None = None
    fecha: str | None = None


class CV(BaseModel):
    nombre: str
    titular: str | None = None
    contacto: Contacto = Contacto()
    resumen: str | None = None
    experiencia: list[Puesto] = []
    educacion: list[Estudio] = []
    habilidades: list[str] = []
    idiomas: list[str] = []
    certificaciones: list[Certificacion] = []
    logros: list[str] = []  # logros aprobados que no estan ligados a un puesto


class Informe(BaseModel):
    cv: CV
    advertencias: list[str]


_NO_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def sanear(cv: CV) -> CV:
    """Quita caracteres de control que no caben en XML ni en PDF (romperian el archivo)."""

    def limpiar(x):
        if isinstance(x, str):
            return _NO_XML.sub("", x)
        if isinstance(x, list):
            return [limpiar(i) for i in x]
        if isinstance(x, dict):
            return {k: limpiar(v) for k, v in x.items()}
        return x

    return CV.model_validate(limpiar(cv.model_dump()))


def _s(v) -> str | None:
    v = str(v).strip() if v is not None else ""
    return v or None


def _fechas(inicio: str | None, fin: str | None) -> str | None:
    if inicio and fin:
        return f"{inicio} – {fin}"
    if inicio:
        return f"Desde {inicio}"
    return f"Hasta {fin}" if fin else None


def _orden_cronologico(f: ExtractedFact) -> int:
    """Clave para ordenar del mas reciente al mas antiguo; sin fecha interpretable, al final."""
    fin = normalize(str(f.data.get("fin") or ""))
    if any(a in fin for a in ACTUAL):
        return 9999
    anios = [
        int(x)
        for x in re.findall(
            r"\b(19\d{2}|20\d{2})\b", f"{f.data.get('fin') or ''} {f.data.get('inicio') or ''}"
        )
    ]
    return max(anios) if anios else 0


def construir(db: Session, profile_id: str) -> Informe:
    perfil = db.get(Profile, profile_id)
    aprobados = review.aprobados(db, profile_id)
    por_cat: dict[str, list[ExtractedFact]] = {}
    for f in aprobados:
        por_cat.setdefault(f.category, []).append(f)
    borradores = list(db.scalars(select(Draft).where(Draft.profile_id == profile_id)))
    ok = [d for d in borradores if d.status == "aprobado"]

    # --- contacto: lo escrito en el perfil manda; los datos de contacto aprobados completan lo que falta
    def contacto_aprobado(tipo: str) -> list[str]:
        return [
            str(f.data.get("valor"))
            for f in por_cat.get("contacto", [])
            if f.data.get("tipo") == tipo and f.data.get("valor")
        ]

    ubic = ", ".join(x for x in (perfil.ciudad, perfil.pais) if x) or ", ".join(
        contacto_aprobado("ciudad")[:1] + contacto_aprobado("pais")[:1]
    )
    enlaces = [f"{e['etiqueta']}: {e['url']}" for e in (perfil.enlaces or [])]
    enlaces += [x for x in contacto_aprobado("enlace") if x not in " ".join(enlaces)]
    contacto = Contacto(
        email=_s(perfil.email) or (contacto_aprobado("email") or [None])[0],
        telefono=_s(perfil.telefono) or (contacto_aprobado("telefono") or [None])[0],
        ubicacion=_s(ubic),
        enlaces=enlaces,
    )

    # --- resumen: un texto aprobado (de la IA o del usuario) o, si no, el que el usuario escribio en su perfil
    resumen = next((d.text for d in ok if d.section == "resumen"), None) or _s(perfil.resumen)

    # --- experiencia, del puesto mas reciente al mas antiguo
    logros = por_cat.get("logro", [])
    usados: set[str] = set()
    puestos: list[Puesto] = []
    for exp in sorted(por_cat.get("experiencia", []), key=_orden_cronologico, reverse=True):
        clave = normalize(review.etiqueta_experiencia(exp))
        puntos: list[str] = []
        for lg in logros:
            if normalize(str(lg.data.get("contexto") or "")) != clave:
                continue
            usados.add(lg.id)
            redactado = next((d.text for d in ok if d.section == "logro" and lg.id in d.source_ids), None)
            puntos.append(redactado or str(lg.data.get("texto")))  # sin texto aprobado: el logro original
        puntos += [
            d.text
            for d in ok
            if d.section == "logro"
            and d.target_fact_id == exp.id
            and d.text not in puntos
            and not any(s in usados for s in d.source_ids)
        ]
        puestos.append(
            Puesto(
                cargo=str(exp.data.get("cargo")),
                empresa=_s(exp.data.get("empresa")),
                fechas=_fechas(_s(exp.data.get("inicio")), _s(exp.data.get("fin"))),
                puntos=puntos,
            )
        )

    habilidades: list[str] = []
    for f in por_cat.get("habilidad", []):
        for n in f.data.get("nombres") or []:
            if normalize(n) not in {normalize(h) for h in habilidades}:
                habilidades.append(n)

    cv = CV(
        nombre=perfil.nombre_completo,
        titular=_s(perfil.titular),
        contacto=contacto,
        resumen=resumen,
        experiencia=puestos,
        educacion=[
            Estudio(
                titulo=str(f.data.get("titulo")),
                institucion=_s(f.data.get("institucion")),
                fecha=_s(f.data.get("fecha_graduacion")),
            )
            for f in por_cat.get("educacion", [])
        ],
        habilidades=habilidades,
        idiomas=[
            f"{f.data.get('idioma')} ({f.data.get('nivel')})"
            if f.data.get("nivel")
            else str(f.data.get("idioma"))
            for f in por_cat.get("idioma", [])
        ],
        certificaciones=[
            Certificacion(
                nombre=str(f.data.get("nombre")),
                emisor=_s(f.data.get("emisor")),
                fecha=_s(f.data.get("fecha")),
            )
            for f in por_cat.get("certificacion", [])
        ],
        logros=[str(lg.data.get("texto")) for lg in logros if lg.id not in usados],
    )
    return Informe(cv=cv, advertencias=_advertencias(db, profile_id, cv, borradores))


def _advertencias(db: Session, profile_id: str, cv: CV, borradores: list[Draft]) -> list[str]:
    a: list[str] = []
    if not cv.resumen:
        a.append("No hay un resumen aprobado: el currículum saldrá sin resumen profesional.")
    if not cv.experiencia:
        a.append("No hay experiencia laboral aprobada.")
    if not cv.contacto.email and not cv.contacto.telefono:
        a.append("Falta un medio de contacto (correo o teléfono).")
    sin_puntos = [p.cargo for p in cv.experiencia if not p.puntos]
    if sin_puntos:
        a.append(
            f"{len(sin_puntos)} puesto(s) sin logros: "
            + ", ".join(sin_puntos[:3])
            + ("…" if len(sin_puntos) > 3 else "")
            + "."
        )
    sin_aprobar = sum(1 for d in borradores if d.status == "borrador")
    if sin_aprobar:
        a.append(f"Hay {sin_aprobar} texto(s) redactado(s) sin aprobar; no se incluyen.")
    pendientes = db.scalar(
        select(ExtractedFact.id)
        .where(ExtractedFact.profile_id == profile_id, ExtractedFact.status == "pendiente")
        .limit(1)
    )
    if pendientes:
        a.append("Hay datos pendientes de revisar; no se incluyen.")
    return a
