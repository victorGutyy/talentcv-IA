"""Base de datos SQLite: motor, sesiones, tipos y migraciones con copia de seguridad."""

import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import DateTime, Engine, TypeDecorator, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Guarda siempre UTC y devuelve datetimes con zona horaria (SQLite no la conserva)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("se requiere un datetime con zona horaria")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_db_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _alembic_config(settings: Settings) -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", settings.db_url)
    return cfg


def migrate(settings: Settings) -> Path | None:
    """Aplica las migraciones pendientes. Antes hace una copia si la BD ya existe.

    Devuelve la ruta de la copia creada, o None si no hizo falta.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    cfg = _alembic_config(settings)
    head = ScriptDirectory.from_config(cfg).get_current_head()

    backup: Path | None = None
    if settings.db_path.exists():
        engine = create_db_engine(settings.db_url)
        try:
            with engine.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
        finally:
            engine.dispose()
        if current != head:
            settings.backups_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = settings.backups_dir / f"talentcv-antes-de-{head}-{stamp}.sqlite3"
            shutil.copy2(settings.db_path, backup)

    try:
        command.upgrade(cfg, "head")
    except Exception:
        if backup is not None:  # restaurar el estado anterior
            shutil.copy2(backup, settings.db_path)
        raise
    return backup


def session_dependency(factory: sessionmaker[Session]):
    def get_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    return get_session
