import logging

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str
    db: str


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Liveness and database check",
    responses={503: {"model": HealthOut, "description": "A dependency is down"}},
)
async def health(db: DbSession, response: Response) -> HealthOut:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        # Log the real reason; never send connection details to the client.
        logger.exception("Health check: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="degraded", db="down")
    return HealthOut(status="ok", db="ok")
