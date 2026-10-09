from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.schemas.errors import ErrorResponse
from app.schemas.me import MeOut
from app.schemas.officer import OfficerOut
from app.schemas.user import UserOut
from app.services.officer_service import OfficerService

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=MeOut,
    summary="Your own profile (officers also get their officer profile)",
    responses={401: {"model": ErrorResponse, "description": "Invalid or missing token"}},
)
async def me(user: CurrentUser, db: DbSession) -> MeOut:
    officer = None
    if user.role == UserRole.OFFICER:
        officer = OfficerOut.model_validate(await OfficerService(db).own_profile(user))
    return MeOut(**UserOut.model_validate(user).model_dump(), officer=officer)
