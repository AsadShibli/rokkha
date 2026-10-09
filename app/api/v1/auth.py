from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginIn, RefreshIn, TokenPair
from app.schemas.errors import ErrorResponse
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Invalid or missing token"}}
DISABLED = {403: {"model": ErrorResponse, "description": "Account disabled"}}


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


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in with phone and password",
    responses={
        401: {"model": ErrorResponse, "description": "Wrong phone or password"},
        **DISABLED,
    },
)
async def login(data: LoginIn, db: DbSession) -> TokenPair:
    return await AuthService(db).login(data.phone, data.password)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Swap a refresh token for a new pair (the old one is revoked)",
    responses={**UNAUTHORIZED, **DISABLED},
)
async def refresh(data: RefreshIn, db: DbSession) -> TokenPair:
    return await AuthService(db).refresh(data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one refresh token",
    responses=UNAUTHORIZED,
)
async def logout(data: RefreshIn, user: CurrentUser, db: DbSession) -> None:
    await AuthService(db).logout(user, data.refresh_token)
