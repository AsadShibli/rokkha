from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AccountDisabledError,
    ForbiddenError,
    InvalidTokenError,
    RateLimitedError,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.rate_limit import NoopRateLimiter, RateLimiter, RedisRateLimiter
from app.services.realtime import EventPublisher, NullPublisher, RedisPublisher
from app.workers.queue import ArqJobQueue, JobQueue, NullJobQueue

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_publisher(request: Request) -> EventPublisher:
    redis = getattr(request.app.state, "redis", None)
    return RedisPublisher(redis) if redis is not None else NullPublisher()


Publisher = Annotated[EventPublisher, Depends(get_publisher)]


def get_job_queue(request: Request) -> JobQueue:
    arq = getattr(request.app.state, "arq", None)
    return ArqJobQueue(arq) if arq is not None else NullJobQueue()


Queue = Annotated[JobQueue, Depends(get_job_queue)]


def get_rate_limiter(request: Request) -> RateLimiter:
    redis = getattr(request.app.state, "redis", None)
    return RedisRateLimiter(redis) if redis is not None else NoopRateLimiter()


# auto_error=False: a missing header reaches our handler and gets the standard error shape.
bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise InvalidTokenError()
    claims = decode_token(credentials.credentials, "access")
    # Load the user on every request (not trust the token's contents), so deactivation and
    # role changes take effect immediately rather than when the token expires.
    user = await UserRepository(db).get(claims.user_id)
    if user is None:
        raise InvalidTokenError()
    if not user.is_active:
        raise AccountDisabledError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency allowing only the given roles (403 FORBIDDEN otherwise)."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return checker


SuperAdmin = Annotated[User, Depends(require_role(UserRole.SUPER_ADMIN))]
StationAdmin = Annotated[User, Depends(require_role(UserRole.STATION_ADMIN))]
AnyAdmin = Annotated[User, Depends(require_role(UserRole.STATION_ADMIN, UserRole.SUPER_ADMIN))]
OfficerUser = Annotated[User, Depends(require_role(UserRole.OFFICER))]
Citizen = Annotated[User, Depends(require_role(UserRole.CITIZEN))]


async def limit_sos(
    citizen: Citizen, limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]
) -> User:
    """BR Incidents-creation 8: at most N SOS attempts per window per citizen (429)."""
    settings = get_settings()
    decision = await limiter.hit(
        f"rate:sos:{citizen.id}", settings.sos_rate_limit, settings.sos_rate_window_seconds
    )
    if not decision.allowed:
        raise RateLimitedError(decision.retry_after)
    return citizen


RateLimitedCitizen = Annotated[User, Depends(limit_sos)]


def get_ai_client(request: Request):
    return getattr(request.app.state, "ai", None)


async def limit_ai_draft(
    citizen: Citizen, limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]
) -> User:
    """Each draft costs money: cap it per citizen (429 with Retry-After)."""
    settings = get_settings()
    decision = await limiter.hit(
        f"rate:ai-draft:{citizen.id}",
        settings.ai_draft_rate_limit,
        settings.ai_draft_rate_window_seconds,
    )
    if not decision.allowed:
        raise RateLimitedError(decision.retry_after)
    return citizen


AiDraftCitizen = Annotated[User, Depends(limit_ai_draft)]
