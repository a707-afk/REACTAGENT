"""Alembic async migration environment for ecom-agent."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db.base import Base

# Import all models so Base.metadata knows about them
import app.db.models.ticket  # noqa: F401
import app.db.models.ticket_event  # noqa: F401
import app.db.models.customer  # noqa: F401
import app.db.models.session  # noqa: F401
import app.db.models.ingestion_job  # noqa: F401
import app.db.models.document  # noqa: F401
import app.db.models.eval_run  # noqa: F401
import app.db.models.eval_case  # noqa: F401
import app.db.models.agent_run  # noqa: F401
import app.db.models.agent_step  # noqa: F401
import app.db.models.approval  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations within a single connection context.

    SQLite needs `render_as_batch=True` for safe ALTER TABLE operations
    and `transaction_per_migration=True` to avoid nested transaction issues.
    """
    url = str(connection.engine.url)
    is_sqlite = "sqlite" in url

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite,          # SQLite: batch mode for ALTER
        transaction_per_migration=True,     # Avoid nested tx issues
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    url = get_url()
    is_sqlite = "sqlite" in url

    connectable = create_async_engine(
        url,
        echo=False,
        poolclass=pool.NullPool if is_sqlite else pool.QueuePool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
