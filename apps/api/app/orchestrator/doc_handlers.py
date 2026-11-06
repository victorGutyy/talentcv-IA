"""Tareas de documentos: lectura (con OCR) y extraccion de datos con evidencia."""

from collections import Counter

from app.ai.base import LLMInvalidOutput, LLMUnavailable
from app.ai.prompting import SYSTEM_BASE, untrusted_block
from app.ai.structured import generate_structured
from app.core.errors import UserFacingError
from app.modules.documents import service as docs
from app.modules.documents.models import PAGE_SEP, Document
from app.modules.documents.reader import read_document
from app.modules.extraction.evidence import DocumentIndex, Rejected, Verified, verify_item
from app.modules.extraction.schemas import CATEGORIAS, INSTRUCCIONES, ExtraccionCV
from app.modules.extraction.service import chunk_pages, save_facts
from app.orchestrator.jobs import JobContext

_TOKENS_ESPERADOS = 700  # para estimar el progreso dentro de un fragmento


def _marcar_error(ctx: JobContext, doc_id: str, mensaje: str) -> None:
    with ctx.session_factory() as db:
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status, doc.error = "error", mensaje
            db.commit()


async def leer_documento(ctx: JobContext) -> dict:
    doc_id = ctx.params["documento_id"]
    with ctx.session_factory() as db:
        doc = docs.get(db, doc_id)
        kind, path = doc.kind, docs.path_of(ctx.settings, doc)

    try:
        result = await read_document(ctx.settings, kind, path, ctx.report)
    except UserFacingError as e:
        _marcar_error(ctx, doc_id, str(e))
        raise
    except Exception:
        _marcar_error(ctx, doc_id, "No se pudo leer el documento.")
        raise

    with ctx.session_factory() as db:
        doc = docs.get(db, doc_id)
        doc.text = PAGE_SEP.join(result.pages)
        doc.page_count = len(result.pages)
        doc.ocr_pages = result.ocr_pages
        doc.status, doc.error = "leido", None
        db.commit()
    return {
        "paginas": len(result.pages),
        "paginas_ocr": result.ocr_pages,
        "caracteres": sum(len(p) for p in result.pages),
    }


async def extraer_datos(ctx: JobContext) -> dict:
    doc_id = ctx.params["documento_id"]
    with ctx.session_factory() as db:
        doc = docs.get(db, doc_id)
        if doc.status != "leido":
            raise UserFacingError("El documento aún no se ha leído correctamente.")
        profile_id, pages, ocr_pages = doc.profile_id, docs.pages_of(doc), list(doc.ocr_pages)

    ctx.report(0.02, "Comprobando el motor de IA…")
    estado = await ctx.provider.health()
    if not estado.available or not estado.model_installed:
        raise LLMUnavailable(estado.error or "El motor de IA no está disponible.")

    index = DocumentIndex(pages)
    chunks = chunk_pages(pages)
    n = len(chunks)
    verified: list[Verified] = []
    rejected: list[Rejected] = []
    fallos = 0

    for i, chunk in enumerate(chunks):
        base = i / n

        def al_generar(k: int, i: int = i, base: float = base) -> None:
            avance = 0.05 + 0.9 * (base + min(k / _TOKENS_ESPERADOS, 1.0) / n)
            ctx.report(avance, f"Analizando el fragmento {i + 1} de {n}… ({k} tokens)")

        ctx.report(0.05 + 0.9 * base, f"Analizando el fragmento {i + 1} de {n}…")
        prompt = INSTRUCCIONES + "\n" + untrusted_block(chunk)
        try:
            salida, _ = await generate_structured(
                ctx.provider, ExtraccionCV, SYSTEM_BASE, prompt, max_tokens=2000, on_token=al_generar
            )
        except LLMInvalidOutput:
            fallos += 1
            continue
        for categoria, (atributo, campos, obligatorios) in CATEGORIAS.items():
            for item in getattr(salida, atributo):
                r = verify_item(categoria, item.model_dump(), campos, obligatorios, index)
                (verified if isinstance(r, Verified) else rejected).append(r)

    if fallos == n:
        raise LLMInvalidOutput("El modelo no pudo analizar el documento. Prueba de nuevo.")

    ctx.report(0.97, "Guardando los datos verificados…")
    with ctx.session_factory() as db:
        guardados = save_facts(db, profile_id, doc_id, verified, ocr_pages)

    return {
        "fragmentos": n,
        "fragmentos_con_error": fallos,
        "hechos": guardados,
        "por_categoria": dict(Counter(v.category for v in verified)),
        "descartados": len(rejected),
        "motivos_descarte": dict(Counter(r.reason for r in rejected)),
    }
