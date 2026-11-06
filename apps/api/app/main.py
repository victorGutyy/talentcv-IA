"""Fabrica de la aplicacion FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai.base import LLMProvider
from app.ai.ollama import OllamaProvider
from app.core.config import Settings
from app.core.db import create_db_engine, make_session_factory, migrate, session_dependency
from app.core.security import TOKEN_HEADER, install_security
from app.modules.documents import service as documents
from app.modules.documents.router import build_router as documents_router
from app.modules.export.router import build_router as export_router
from app.modules.extraction.router import build_router as extraction_router
from app.modules.interview.router import build_router as interview_router
from app.modules.profiles.router import build_router as profiles_router
from app.modules.writing.router import build_router as writing_router
from app.orchestrator.handlers import default_handlers
from app.orchestrator.jobs import JobManager
from app.orchestrator.router import build_router as tasks_router


def create_app(
    settings: Settings | None = None,
    *,
    run_migrations: bool = True,
    provider: LLMProvider | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if run_migrations:
        migrate(settings)

    engine = create_db_engine(settings.db_url)
    session_factory = make_session_factory(engine)
    get_session = session_dependency(session_factory)

    provider = provider or OllamaProvider(settings)
    jobs = JobManager(session_factory, provider, default_handlers(), settings)
    jobs.recover()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await jobs.shutdown()
        aclose = getattr(provider, "aclose", None)
        if aclose:
            await aclose()

    app = FastAPI(
        title="TalentCV AI",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_security(app, settings)
    if settings.dev_origins:  # solo desarrollo; vacio en la app instalada
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.dev_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=[TOKEN_HEADER, "content-type"],
        )
    app.include_router(
        profiles_router(
            get_session, before_delete=lambda db, pid: documents.purge_profile_files(db, settings, pid)
        )
    )
    app.include_router(tasks_router(provider, jobs))
    app.include_router(documents_router(get_session, settings, jobs))
    app.include_router(extraction_router(get_session))
    app.include_router(interview_router(get_session))
    app.include_router(writing_router(get_session, jobs))
    app.include_router(export_router(get_session))

    @app.get("/api/estado")
    def estado():
        return {"ok": True, "version": __version__}

    # La interfaz estatica va al final para que /api/* tenga prioridad.
    if settings.web_dir and settings.web_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")

    app.state.engine = engine
    app.state.jobs = jobs
    return app
