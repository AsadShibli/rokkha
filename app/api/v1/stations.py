from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, SuperAdmin
from app.schemas.common import Page, PageParams, page_params
from app.schemas.errors import ErrorResponse
from app.schemas.station import StationCreate, StationOut
from app.schemas.user import UserCreate, UserOut
from app.services.station_service import StationService

router = APIRouter(prefix="/stations", tags=["stations"])

ERRORS = {
    401: {"model": ErrorResponse, "description": "Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Role not allowed"},
}
CONFLICT = {409: {"model": ErrorResponse, "description": "Unique value already used"}}


@router.get(
    "",
    response_model=Page[StationOut],
    summary="List stations (any logged-in user; citizens pick one when filing a GD)",
    responses=ERRORS,
)
async def list_stations(
    _: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    city: Annotated[str | None, Query(max_length=60)] = None,
) -> Page[StationOut]:
    items, total = await StationService(db).list(params, city)
    return Page(
        items=[StationOut.model_validate(s) for s in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "",
    response_model=StationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a station (super admin)",
    responses={**ERRORS, **CONFLICT},
)
async def create_station(data: StationCreate, _: SuperAdmin, db: DbSession) -> StationOut:
    station = await StationService(db).create(data)
    return StationOut.model_validate(station)


@router.post(
    "/{station_id}/admins",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a station admin account (super admin)",
    responses={
        **ERRORS,
        **CONFLICT,
        404: {"model": ErrorResponse, "description": "Station not found"},
    },
)
async def create_station_admin(
    station_id: int, data: UserCreate, _: SuperAdmin, db: DbSession
) -> UserOut:
    user = await StationService(db).create_admin(station_id, data)
    return UserOut.model_validate(user)
