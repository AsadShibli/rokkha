from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Citizen, DbSession, StationAdmin, require_role
from app.models.enums import GdCategory, GdStatus, UserRole
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.errors import ErrorResponse
from app.schemas.gd import GdCreate, GdOut, GdReviewIn
from app.services.gd_service import GdService

router = APIRouter(prefix="/gds", tags=["online GD"])

# Officers never see GDs (BR Roles); everyone else is scoped in the service.
GdReader = Annotated[
    User,
    Depends(require_role(UserRole.CITIZEN, UserRole.STATION_ADMIN, UserRole.SUPER_ADMIN)),
]
AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Role not allowed"},
}
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Not found or not yours"}}


@router.post(
    "",
    response_model=GdOut,
    status_code=status.HTTP_201_CREATED,
    summary="File an Online GD; returns its number, e.g. SYL-KOT-2026-000123",
    responses=AUTH_ERRORS,
)
async def file_gd(data: GdCreate, citizen: Citizen, db: DbSession) -> GdOut:
    return GdOut.model_validate(await GdService(db).file(citizen, data))


@router.get(
    "",
    response_model=Page[GdOut],
    summary="List GDs you may see (citizen: own; station admin: station; super admin: all)",
    responses=AUTH_ERRORS,
)
async def list_gds(
    user: GdReader,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[GdStatus | None, Query(alias="status")] = None,
    category: GdCategory | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    station_id: Annotated[int | None, Query(description="Super admin only")] = None,
) -> Page[GdOut]:
    items, total = await GdService(db).list_visible(
        user,
        params,
        status=status_,
        category=category,
        station_id=station_id,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(
        items=[GdOut.model_validate(g) for g in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{gd_number}",
    response_model=GdOut,
    summary="One GD by its number",
    responses={**AUTH_ERRORS, **NOT_FOUND},
)
async def get_gd(gd_number: str, user: GdReader, db: DbSession) -> GdOut:
    return GdOut.model_validate(await GdService(db).get_visible(user, gd_number))


@router.patch(
    "/{gd_number}/review",
    response_model=GdOut,
    summary="Station admin: start_review, approve, or reject (note required)",
    responses={
        **AUTH_ERRORS,
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Not allowed from current status"},
    },
)
async def review_gd(gd_number: str, data: GdReviewIn, admin: StationAdmin, db: DbSession) -> GdOut:
    return GdOut.model_validate(await GdService(db).review(admin, gd_number, data))
