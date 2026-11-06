"""Rutas de documentos. La subida usa el cuerpo crudo (sin multipart) con un tope de tamano."""

from collections.abc import Callable
from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.documents import service
from app.modules.documents.files import InvalidFile
from app.modules.documents.models import Document
from app.orchestrator.jobs import JobManager
from app.orchestrator.router import TareaOut
from app.orchestrator.router import _out as tarea_out


class DocumentOut(BaseModel):
    id: str
    perfil_id: str
    nombre: str
    tipo: str
    tamano: int
    estado: str
    paginas: int
    paginas_ocr: list[int]
    error: str | None
    creado_en: datetime


class SubidaOut(BaseModel):
    documento: DocumentOut
    tarea: TareaOut


class TextoOut(BaseModel):
    paginas: list[str]


def _out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        perfil_id=d.profile_id,
        nombre=d.original_name,
        tipo=d.kind,
        tamano=d.size_bytes,
        estado=d.status,
        paginas=d.page_count,
        paginas_ocr=d.ocr_pages,
        error=d.error,
        creado_en=d.created_at,
    )


async def _read_limited(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise InvalidFile(f"El archivo supera el máximo de {limit // (1024 * 1024)} MB.")
    chunks, total = [], 0
    async for part in request.stream():
        total += len(part)
        if total > limit:
            raise InvalidFile(f"El archivo supera el máximo de {limit // (1024 * 1024)} MB.")
        chunks.append(part)
    return b"".join(chunks)


def build_router(get_session: Callable[..., Session], settings: Settings, jobs: JobManager) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["documentos"])

    def _o404(fn, *args):
        try:
            return fn(*args)
        except service.DocumentNotFound:
            raise HTTPException(status_code=404, detail="Documento no encontrado") from None

    @router.post(
        "/perfiles/{profile_id}/documentos", response_model=SubidaOut, status_code=status.HTTP_201_CREATED
    )
    async def subir(
        profile_id: str,
        request: Request,
        nombre: str = Query(default="documento", max_length=300),
        db: Session = Depends(get_session),
    ):
        try:
            data = await _read_limited(request, settings.max_upload_bytes)
            doc = service.create(db, settings, profile_id, unquote(nombre), data)
        except InvalidFile as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        except service.ProfileMissing:
            raise HTTPException(status_code=404, detail="Perfil no encontrado") from None
        except service.DuplicateDocument:
            raise HTTPException(
                status_code=409, detail="Este documento ya fue subido a este perfil."
            ) from None
        job = jobs.submit("leer_documento", {"documento_id": doc.id})
        return SubidaOut(documento=_out(doc), tarea=tarea_out(job))

    @router.get("/perfiles/{profile_id}/documentos", response_model=list[DocumentOut])
    def listar(profile_id: str, db: Session = Depends(get_session)):
        return [_out(d) for d in service.list_for_profile(db, profile_id)]

    @router.get("/documentos/{doc_id}", response_model=DocumentOut)
    def obtener(doc_id: str, db: Session = Depends(get_session)):
        return _out(_o404(service.get, db, doc_id))

    @router.get("/documentos/{doc_id}/texto", response_model=TextoOut)
    def texto(doc_id: str, db: Session = Depends(get_session)):
        return TextoOut(paginas=service.pages_of(_o404(service.get, db, doc_id)))

    @router.delete("/documentos/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
    def eliminar(doc_id: str, db: Session = Depends(get_session)):
        _o404(service.delete, db, settings, doc_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/documentos/{doc_id}/extraer", response_model=TareaOut, status_code=status.HTTP_202_ACCEPTED
    )
    async def extraer(doc_id: str, db: Session = Depends(get_session)):
        doc = _o404(service.get, db, doc_id)
        if doc.status != "leido":
            raise HTTPException(status_code=409, detail="El documento aún no se ha leído correctamente.")
        return tarea_out(jobs.submit("extraer_datos", {"documento_id": doc_id}))

    return router
