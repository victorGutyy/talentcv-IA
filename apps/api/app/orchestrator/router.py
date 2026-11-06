"""Rutas de estado de la IA y de tareas en segundo plano."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.base import LLMProvider
from app.orchestrator.jobs import JobManager, JobNotFound, UnknownJobKind
from app.orchestrator.models import Job


class EstadoIA(BaseModel):
    disponible: bool
    proveedor: str
    url: str
    modelo: str
    modelo_instalado: bool
    version: str | None
    modelos: list[str]
    error: str | None


class TareaIn(BaseModel):
    tipo: str = Field(max_length=60)


class TareaOut(BaseModel):
    id: str
    tipo: str
    estado: str
    progreso: float
    mensaje: str
    resultado: dict | None
    error: str | None
    creada_en: datetime
    iniciada_en: datetime | None
    terminada_en: datetime | None


def _out(j: Job) -> TareaOut:
    return TareaOut(
        id=j.id,
        tipo=j.kind,
        estado=j.status,
        progreso=j.progress,
        mensaje=j.message,
        resultado=j.result,
        error=j.error,
        creada_en=j.created_at,
        iniciada_en=j.started_at,
        terminada_en=j.finished_at,
    )


def build_router(provider: LLMProvider, jobs: JobManager) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["ia"])

    @router.get("/ia/estado", response_model=EstadoIA)
    async def estado_ia():
        h = await provider.health()
        return EstadoIA(
            disponible=h.available,
            proveedor=h.provider,
            url=h.url,
            modelo=h.model,
            modelo_instalado=h.model_installed,
            version=h.version,
            modelos=h.models,
            error=h.error,
        )

    @router.post("/tareas", response_model=TareaOut, status_code=status.HTTP_202_ACCEPTED)
    async def crear_tarea(data: TareaIn):
        try:
            return _out(jobs.submit(data.tipo))
        except UnknownJobKind:
            raise HTTPException(status_code=422, detail=f"Tipo de tarea desconocido: {data.tipo}") from None

    @router.get("/tareas", response_model=list[TareaOut])
    async def listar_tareas():
        return [_out(j) for j in jobs.recent()]

    @router.get("/tareas/{job_id}", response_model=TareaOut)
    async def obtener_tarea(job_id: str):
        try:
            return _out(jobs.get(job_id))
        except JobNotFound:
            raise HTTPException(status_code=404, detail="Tarea no encontrada") from None

    @router.post("/tareas/{job_id}/cancelar", response_model=TareaOut)
    async def cancelar_tarea(job_id: str):
        try:
            return _out(jobs.cancel(job_id))
        except JobNotFound:
            raise HTTPException(status_code=404, detail="Tarea no encontrada") from None

    return router
