from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AnyAdmin, DbSession, OfficerUser, StationAdmin
from app.models.enums import DutyStatus
from app.schemas.common import Page, PageParams, page_params
from app.schemas.errors import ErrorResponse
from app.schemas.officer import LocationIn, OfficerCreate, OfficerOut, OfficerStatusIn
from app.services.officer_service import OfficerService

router = APIRouter(prefix="/officers", tags=["officers"])

ERRORS = {
    401: {"model": ErrorResponse, "description": "Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Role not allowed"},
}


@router.get(
    "",
    response_model=Page[OfficerOut],
    summary="List officers (station admin: own station; super admin: all)",
    responses=ERRORS,
)
async def list_officers(
    caller: AnyAdmin,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    duty_status: DutyStatus | None = None,
    station_id: Annotated[
        int | None, Query(description="Super admin only; ignored for station admins")
    ] = None,
) -> Page[OfficerOut]:
    items, total = await OfficerService(db).list(caller, params, station_id, duty_status)
    return Page(
        items=[OfficerOut.model_validate(o) for o in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "",
    response_model=OfficerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an officer in your station (station admin)",
    responses={
        **ERRORS,
        409: {"model": ErrorResponse, "description": "Phone, email or badge_no already used"},
    },
)
async def create_officer(data: OfficerCreate, admin: StationAdmin, db: DbSession) -> OfficerOut:
    officer = await OfficerService(db).create(admin, data)
    return OfficerOut.model_validate(officer)


@router.patch(
    "/me/status",
    response_model=OfficerOut,
    summary="Go on or off duty (officer)",
    responses={
        **ERRORS,
        409: {"model": ErrorResponse, "description": "Officer is busy with an incident"},
    },
)
async def set_my_status(data: OfficerStatusIn, user: OfficerUser, db: DbSession) -> OfficerOut:
    officer = await OfficerService(db).set_duty_status(user, DutyStatus(data.duty_status))
    return OfficerOut.model_validate(officer)


@router.patch(
    "/me/location",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Send current location (officer)",
    responses=ERRORS,
)
async def update_my_location(data: LocationIn, user: OfficerUser, db: DbSession) -> None:
    await OfficerService(db).update_location(user, data.lat, data.lng)
