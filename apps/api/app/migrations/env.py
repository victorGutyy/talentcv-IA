"""Entorno de Alembic. Se ejecuta de forma programatica desde app.core.db.migrate()."""

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.modules.documents.models  # noqa: F401
import app.modules.extraction.models  # noqa: F401
import app.modules.interview.models  # noqa: F401
import app.modules.profiles.models  # noqa: F401  (registra las tablas en Base.metadata)
import app.orchestrator.models  # noqa: F401
from app.core.db import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
