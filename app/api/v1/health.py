import logging

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str
    db: str
    redis: str


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Liveness plus database and Redis checks",
    responses={503: {"model": HealthOut, "description": "A dependency is down"}},
)
async def health(db: DbSession, request: Request, response: Response) -> HealthOut:
    db_state = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        # Log the real reason; never send connection details to the client.
        logger.exception("Health check: database unreachable")
        db_state = "down"

    redis = getattr(request.app.state, "redis", None)
    redis_state = "not_configured"
    if redis is not None:
        try:
            await redis.ping()
            redis_state = "ok"
        except Exception:
            logger.exception("Health check: Redis unreachable")
            redis_state = "down"

    healthy = db_state == "ok" and redis_state != "down"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degraded", db=db_state, redis=redis_state)
