"""Gestor de tareas en segundo plano.

El modelo local en CPU tarda decenas de segundos o minutos, asi que toda operacion
de IA es una tarea: se lanza, se consulta su progreso y puede cancelarse.
Solo corre una tarea de IA a la vez (max_concurrent=1): el equipo no da para mas.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.base import LLMError, LLMProvider
from app.core.config import Settings
from app.core.db import utcnow
from app.core.errors import UserFacingError
from app.orchestrator.models import ACTIVE, Job

log = logging.getLogger("talentcv.jobs")

Handler = Callable[["JobContext"], Awaitable[dict]]


class UnknownJobKind(ValueError):
    pass


class JobNotFound(Exception):
    pass


@dataclass
class JobContext:
    job_id: str
    params: dict
    provider: LLMProvider
    settings: Settings
    session_factory: sessionmaker[Session]
    _report: Callable[[str, float, str | None], None] = field(repr=False)

    def report(self, progress: float, message: str | None = None) -> None:
        self._report(self.job_id, max(0.0, min(progress, 1.0)), message)


class JobManager:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: LLMProvider,
        handlers: dict[str, Handler],
        settings: Settings,
        *,
        max_concurrent: int = 1,
    ):
        self._settings = settings
        self._sf = session_factory
        self._provider = provider
        self._handlers = handlers
        self._sem = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, asyncio.Task] = {}
        self._last_write: dict[str, float] = {}

    # ---- consulta -------------------------------------------------------
    @property
    def kinds(self) -> list[str]:
        return sorted(self._handlers)

    def get(self, job_id: str) -> Job:
        with self._sf() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise JobNotFound(job_id)
            return job

    def recent(self, limit: int = 20) -> list[Job]:
        with self._sf() as db:
            return list(db.scalars(select(Job).order_by(Job.created_at.desc(), Job.id).limit(limit)))

    # ---- ciclo de vida --------------------------------------------------
    def recover(self) -> int:
        """Al arrancar: las tareas que quedaron activas por un cierre brusco pasan a 'interrumpido'."""
        with self._sf() as db:
            rows = list(db.scalars(select(Job).where(Job.status.in_(ACTIVE))))
            for j in rows:
                j.status, j.message, j.finished_at = (
                    "interrumpido",
                    "La aplicación se cerró durante la tarea.",
                    utcnow(),
                )
            db.commit()
            return len(rows)

    def submit(self, kind: str, params: dict | None = None) -> Job:
        """Crea la tarea y la lanza. Debe llamarse desde el bucle de eventos (endpoint async)."""
        if kind not in self._handlers:
            raise UnknownJobKind(kind)
        with self._sf() as db:
            job = Job(kind=kind, params=params or {}, message="En cola")
            db.add(job)
            db.commit()
        self._tasks[job.id] = asyncio.create_task(self._run(job.id), name=f"job-{job.id}")
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()  # _run registra el estado 'cancelado'
        elif job.status in ACTIVE:  # huerfana: sin tarea viva
            self._update(job_id, status="cancelado", message="Cancelada.", finished_at=utcnow())
        return self.get(job_id)

    async def shutdown(self) -> None:
        tasks = [t for t in self._tasks.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---- ejecucion ------------------------------------------------------
    def _update(self, job_id: str, **fields) -> None:
        with self._sf() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            for k, v in fields.items():
                setattr(job, k, v)
            db.commit()

    def _report(self, job_id: str, progress: float, message: str | None) -> None:
        now = time.monotonic()
        if progress < 1.0 and now - self._last_write.get(job_id, 0.0) < 0.4:
            return  # limitar escrituras a SQLite
        self._last_write[job_id] = now
        fields: dict = {"progress": progress}
        if message is not None:
            fields["message"] = message[:300]
        self._update(job_id, **fields)

    async def _run(self, job_id: str) -> None:
        try:
            async with self._sem:
                job = self.get(job_id)
                self._update(job_id, status="ejecutando", started_at=utcnow(), message="Iniciando…")
                ctx = JobContext(
                    job_id, dict(job.params), self._provider, self._settings, self._sf, self._report
                )
                result = await self._handlers[job.kind](ctx)
            self._update(
                job_id,
                status="completado",
                progress=1.0,
                message="Listo",
                result=result,
                finished_at=utcnow(),
            )
        except asyncio.CancelledError:
            self._update(
                job_id, status="cancelado", message="Cancelada por el usuario.", finished_at=utcnow()
            )
        except (LLMError, UserFacingError) as e:
            self._update(
                job_id, status="error", message="No se pudo completar.", error=str(e), finished_at=utcnow()
            )
        except Exception:  # noqa: BLE001 - no filtrar detalles internos al usuario
            log.exception("Fallo inesperado en la tarea %s", job_id)
            self._update(
                job_id,
                status="error",
                message="No se pudo completar.",
                error="Error interno inesperado.",
                finished_at=utcnow(),
            )
        finally:
            self._tasks.pop(job_id, None)
            self._last_write.pop(job_id, None)
