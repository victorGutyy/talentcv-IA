"""Tarea de redaccion: el Constructor de perfil (resumen) y el Optimizador (puntos de logros),
siempre pasando por el Auditor. Todo lo que genera la IA queda como BORRADOR."""

from collections.abc import Callable

from pydantic import BaseModel

from app.ai.base import LLMUnavailable
from app.ai.prompting import untrusted_block
from app.ai.structured import generate_structured
from app.core.errors import UserFacingError
from app.modules.extraction import review
from app.modules.writing import audit, service
from app.modules.writing.prompts import (
    MAX_OBJETIVO,
    MAX_PUNTO,
    MAX_RESUMEN,
    SYSTEM_REDACCION,
    PuntoOut,
    ResumenOut,
    correccion,
    prompt_punto,
    prompt_resumen,
)
from app.orchestrator.jobs import JobContext

_TOKENS_ESPERADOS = 120


async def _redactar(
    ctx: JobContext,
    schema: type[BaseModel],
    prompt: str,
    texto_de: Callable[[BaseModel], str],
    fuentes: list[str],
    max_chars: int,
    max_tokens: int,
    on_token: Callable[[int], None],
) -> tuple[str, audit.AuditResult]:
    """Genera, audita y, si hay problemas, reintenta UNA vez indicando que sobra. Devuelve el mejor intento."""

    async def intento(p: str) -> tuple[str, audit.AuditResult]:
        salida, _ = await generate_structured(
            ctx.provider, schema, SYSTEM_REDACCION, p, max_tokens=max_tokens, on_token=on_token
        )
        texto = texto_de(salida).strip()
        return texto, audit.auditar(texto, fuentes, max_chars=max_chars)

    texto, r = await intento(prompt)
    if not r.ok:
        texto2, r2 = await intento(prompt + correccion([i.detalle for i in r.issues]))
        if len(r2.issues) < len(r.issues):
            return texto2, r2
    return texto, r


async def redactar_perfil(ctx: JobContext) -> dict:
    pid = ctx.params["perfil_id"]
    objetivo = (ctx.params.get("puesto_objetivo") or "").strip()[:MAX_OBJETIVO]

    ctx.report(0.02, "Comprobando el motor de IA…")
    estado = await ctx.provider.health()
    if not estado.available or not estado.model_installed:
        raise LLMUnavailable(estado.error or "El motor de IA no está disponible.")

    with ctx.session_factory() as db:
        m = service.cargar(db, pid)
        if not m.hay_datos:
            raise UserFacingError(
                "Primero aprueba algunos datos en «Revisar datos»: la redacción solo usa información aprobada."
            )
        service.limpiar_ia_no_aprobada(db, pid)
        hacer_resumen = not service.tiene_aprobado(db, pid, "resumen")
        trabajos = [
            (e, lg) for e, lg in service.puntos(m) if not service.tiene_aprobado(db, pid, "logro", lg.id)
        ]
        datos = service.bloque_datos(m)
        fuentes_res = service.fuentes_resumen(m)
        nombres = {e.id: review.etiqueta_experiencia(e) for e, _ in trabajos}

    total = int(hacer_resumen) + len(trabajos)
    hecho = 0
    creados = con_problemas = 0

    def progreso(n: int, etiqueta: str) -> None:
        avance = 0.05 + 0.9 * (hecho + min(n / _TOKENS_ESPERADOS, 1.0)) / max(total, 1)
        ctx.report(avance, f"{etiqueta}… ({n} tokens)")

    if hacer_resumen:
        ctx.report(0.05, "Redactando el resumen profesional…")
        bloque_obj = untrusted_block(objetivo) if objetivo else None
        texto, r = await _redactar(
            ctx,
            ResumenOut,
            prompt_resumen(untrusted_block(datos), bloque_obj),
            lambda s: s.resumen,
            fuentes_res,
            MAX_RESUMEN,
            400,
            lambda n: progreso(n, "Redactando el resumen"),
        )
        with ctx.session_factory() as db:
            service.guardar(db, pid, "resumen", texto, r, source_ids=[])
        creados += 1
        con_problemas += int(not r.ok)
        hecho += 1

    for i, (exp, logro) in enumerate(trabajos, start=1):
        etiqueta = f"Mejorando el punto {i} de {len(trabajos)}"
        ctx.report(0.05 + 0.9 * hecho / max(total, 1), etiqueta + "…")
        texto, r = await _redactar(
            ctx,
            PuntoOut,
            prompt_punto(nombres[exp.id], untrusted_block(str(logro.data.get("texto")))),
            lambda s: s.texto,
            service.fuentes_punto(exp, logro),
            MAX_PUNTO,
            250,
            lambda n, e=etiqueta: progreso(n, e),
        )
        with ctx.session_factory() as db:
            service.guardar(db, pid, "logro", texto, r, target_fact_id=exp.id, source_ids=[logro.id])
        creados += 1
        con_problemas += int(not r.ok)
        hecho += 1

    return {
        "borradores": creados,
        "con_problemas": con_problemas,
        "sin_puntos_porque": None if trabajos else "No hay logros aprobados ligados a un puesto.",
    }
