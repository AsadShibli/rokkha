from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AnyAdmin, DbSession
from app.schemas.dashboard import DashboardOut
from app.schemas.errors import ErrorResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/stats",
    response_model=DashboardOut,
    summary="Counts and average response time (station admin: own station; super admin: any)",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing token"},
        403: {"model": ErrorResponse, "description": "Role not allowed"},
    },
)
async def stats(
    user: AnyAdmin,
    db: DbSession,
    station_id: Annotated[int | None, Query(description="Super admin only")] = None,
) -> DashboardOut:
    return await DashboardService(db).stats(user, station_id)
