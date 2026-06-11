"""arq Worker entry point.

Run with: ``python -m app.worker.worker``

The worker connects to Redis, polls the ``default`` queue, and
executes tasks defined in ``app.worker.tasks``.
"""
from __future__ import annotations

import logging
import os
import sys

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from app.config import get_settings

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Called once when the worker starts."""
    logger.info("Worker starting up")


async def shutdown(ctx: dict) -> None:
    """Called once when the worker shuts down."""
    logger.info("Worker shutting down")


async def on_job_start(ctx: dict) -> None:
    """Called before each job."""
    logger.info("Job %s starting", ctx.get("job_id"))


async def on_job_end(ctx: dict) -> None:
    """Called after each job."""
    logger.info("Job %s finished", ctx.get("job_id"))


def get_worker_settings() -> dict:
    """Build the arq Worker settings dict from our config."""
    settings = get_settings()
    redis_url = settings.redis_url
    # Parse redis://host:port/db
    # arq expects RedisSettings(host, port, database, password)
    from urllib.parse import urlparse
    parsed = urlparse(redis_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    database = int(parsed.path.lstrip("/") or "0")
    password = settings.redis_password or parsed.password or None

    return {
        "functions": [
            # Import task functions
            _import_task("ingest_document"),
            _import_task("run_eval"),
            _import_task("process_agent_job"),
        ],
        "redis_settings": RedisSettings(
            host=host,
            port=port,
            database=database,
            password=password,
        ),
        "on_startup": startup,
        "on_shutdown": shutdown,
        "on_job_start": on_job_start,
        "on_job_end": on_job_end,
        "max_jobs": 10,
        "job_timeout": 600,  # 10 minutes
        "keep_result": 3600,  # Keep results for 1 hour
    }


def _import_task(name: str):
    """Lazily import a task function by name from app.worker.tasks."""
    from app.worker import tasks as tasks_module
    return getattr(tasks_module, name)


class WorkerSettings:
    """arq convention: the module-level class or dict named ``WorkerSettings``
    is auto-discovered by ``arq`` CLI.

    We use a class so arq can inspect it via ``WorkerSettings.functions`` etc.
    """

    @staticmethod
    def _build():
        return get_worker_settings()

    @classmethod
    def get_functions(cls):
        return cls._build()["functions"]

    @classmethod
    def get_redis_settings(cls):
        return cls._build()["redis_settings"]


def main():
    """Run the arq worker."""
    settings = get_worker_settings()
    worker = Worker(
        functions=settings["functions"],
        redis_settings=settings["redis_settings"],
        on_startup=settings.get("on_startup"),
        on_shutdown=settings.get("on_shutdown"),
        on_job_start=settings.get("on_job_start"),
        on_job_end=settings.get("on_job_end"),
        max_jobs=settings.get("max_jobs", 10),
        job_timeout=settings.get("job_timeout", 600),
        keep_result=settings.get("keep_result", 3600),
    )
    worker.run()


if __name__ == "__main__":
    main()
