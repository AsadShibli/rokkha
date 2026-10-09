from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import engine
from app.schemas.errors import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_url = get_settings().redis_url
    app.state.redis = Redis.from_url(redis_url, decode_responses=True)
    app.state.arq = await create_pool(RedisSettings.from_dsn(redis_url))
    yield
    await app.state.arq.aclose()
    await app.state.redis.aclose()
    await engine.dispose()


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
