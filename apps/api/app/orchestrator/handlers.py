"""Tareas registradas en el orquestador. Cada rol del producto (analista, entrevistador,
constructor, optimizador, auditor) se anadira aqui como un handler mas."""

from pydantic import BaseModel

from app.ai.base import LLMUnavailable
from app.ai.prompting import SYSTEM_BASE, untrusted_block
from app.ai.structured import generate_structured
from app.orchestrator.jobs import Handler, JobContext

# Documento ficticio con una trampa: NO dice cuando se graduo la persona.
_TEXTO_PRUEBA = (
    "Laura Méndez Ríos\n"
    "Desarrolladora de software en Tecnosur desde 2020.\n"
    "Estudió Ingeniería Informática en la Universidad del Norte.\n"
)
_TOKENS_ESPERADOS = 70


class SalidaDiagnostico(BaseModel):
    nombre: str | None = None
    cargo: str | None = None
    anio_inicio: int | None = None
    fecha_graduacion: str | None = None


async def diagnostico_ia(ctx: JobContext) -> dict:
    """Prueba de extremo a extremo del motor de IA: disponibilidad, velocidad, JSON valido
    y que NO invente un dato ausente."""
    ctx.report(0.03, "Comprobando el motor de IA…")
    estado = await ctx.provider.health()
    if not estado.available or not estado.model_installed:
        raise LLMUnavailable(estado.error or "El motor de IA no está disponible.")

    ctx.report(0.08, "Cargando el modelo y analizando un documento de prueba…")
    prompt = (
        "Extrae del documento estos campos:\n"
        "- nombre: nombre completo de la persona.\n"
        "- cargo: el puesto de trabajo actual (por ejemplo «Analista de datos»).\n"
        "- anio_inicio: el año (número) en que empezó en ese puesto.\n"
        "- fecha_graduacion: la fecha en que terminó sus estudios.\n"
        "Copia los datos tal como aparecen. Usa null solo si el dato NO está en el documento.\n\n"
        + untrusted_block(_TEXTO_PRUEBA)
    )

    def al_generar(n: int) -> None:
        ctx.report(0.1 + 0.85 * min(n / _TOKENS_ESPERADOS, 1.0), f"Generando respuesta… ({n} tokens)")

    salida, res = await generate_structured(
        ctx.provider, SalidaDiagnostico, SYSTEM_BASE, prompt, max_tokens=200, on_token=al_generar
    )
    verificaciones = {
        "extrae_el_nombre": bool(salida.nombre and "Laura" in salida.nombre),
        "extrae_el_anio": salida.anio_inicio == 2020,
        "no_inventa_la_fecha_de_graduacion": salida.fecha_graduacion is None,
    }
    return {
        "modelo": ctx.provider.model,
        "salida": salida.model_dump(),
        "verificaciones": verificaciones,
        "ok": all(verificaciones.values()),
        "tokens_entrada": res.prompt_tokens,
        "tokens_salida": res.output_tokens,
        "tokens_por_segundo": round(res.tokens_per_second, 1),
        "segundos": round(res.total_seconds, 1),
    }


def default_handlers() -> dict[str, Handler]:
    return {"diagnostico_ia": diagnostico_ia}
