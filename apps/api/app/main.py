"""Fabrica de la aplicacion FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import Settings
from app.core.db import create_db_engine, make_session_factory, migrate, session_dependency
from app.core.security import TOKEN_HEADER, install_security
from app.modules.profiles.router import build_router as profiles_router


def create_app(settings: Settings | None = None, *, run_migrations: bool = True) -> FastAPI:
    settings = settings or Settings()
    if run_migrations:
        migrate(settings)

    engine = create_db_engine(settings.db_url)
    get_session = session_dependency(make_session_factory(engine))

    app = FastAPI(title="TalentCV AI", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    install_security(app, settings)
    if settings.dev_origins:  # solo desarrollo; vacio en la app instalada
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.dev_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=[TOKEN_HEADER, "content-type"],
        )
    app.include_router(profiles_router(get_session))

    @app.get("/api/estado")
    def estado():
        return {"ok": True, "version": __version__}

    # La interfaz estatica va al final para que /api/* tenga prioridad.
    if settings.web_dir and settings.web_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")

    app.state.engine = engine
    return app
