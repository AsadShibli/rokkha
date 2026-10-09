from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.errors import ErrorResponse
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a citizen account",
    responses={409: {"model": ErrorResponse, "description": "Phone or email already used"}},
)
async def register(data: UserCreate, db: DbSession) -> UserOut:
    user = await AuthService(db).register(data)
    return UserOut.model_validate(user)
