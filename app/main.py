import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import engine
from app.schemas.errors import ErrorResponse
from app.workers.main import WorkerSettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    redis_url = settings.redis_url
    app.state.ai = (
        anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.ai_timeout_seconds,
            max_retries=0,  # the citizen is waiting; fail fast and let them type instead
        )
        if settings.anthropic_api_key
        else None
    )
    app.state.redis = Redis.from_url(redis_url, decode_responses=True)
    app.state.arq = await create_pool(RedisSettings.from_dsn(redis_url))
    worker, worker_task = None, None
    if settings.run_worker_in_process:
        # Free hosts give one service: run escalation jobs here instead of a separate worker.
        worker = Worker(
            functions=WorkerSettings.functions,
            on_startup=WorkerSettings.on_startup,
            on_shutdown=WorkerSettings.on_shutdown,
            redis_settings=RedisSettings.from_dsn(redis_url),
            handle_signals=False,  # Uvicorn owns the process signals
        )
        worker_task = asyncio.create_task(worker.async_run())
        logger.info("ARQ worker running in-process")
    app.state.worker_task = worker_task
    yield
    if worker is not None:
        await stop_worker(worker, worker_task)
    await app.state.arq.aclose()
    if app.state.ai is not None:
        await app.state.ai.close()
    await app.state.redis.aclose()
    # Closed clients must not be reused by a later app start (e.g. in tests).
    app.state.redis = app.state.arq = app.state.ai = app.state.worker_task = None
    await engine.dispose()


async def stop_worker(worker: Worker, task: asyncio.Task) -> None:
    if hasattr(signal, "SIGUSR1"):
        await worker.close()  # arq's own shutdown (POSIX: Linux containers)
        task.cancel()
        return
    # Windows dev: arq's close() relies on SIGUSR1, so cancel and clean up by hand.
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    if "engine" in worker.ctx:
        await WorkerSettings.on_shutdown(worker.ctx)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Public-safety dispatch and Online GD backend.",
        lifespan=lifespan,
        # Every endpoint can fail validation; show the real error shape instead of FastAPI's.
        responses={422: {"model": ErrorResponse, "description": "Validation error"}},
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
