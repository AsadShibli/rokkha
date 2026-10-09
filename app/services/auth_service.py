from datetime import UTC, datetime

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AccountDisabledError,
    ConflictError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_password_hash,
    verify_password,
)
from app.db.errors import commit_or_conflict
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate
from app.services.user_service import UserService


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.accounts = UserService(session)

    async def register(self, data: UserCreate) -> User:
        """Create a citizen account (BR Accounts 1-4). The client can't pick the role."""
        clashes = await self.accounts.taken_fields(data.phone, data.email)
        if clashes:
            raise ConflictError(details=clashes)
        user = await self.accounts.build_account(data, UserRole.CITIZEN)
        await commit_or_conflict(self.session)
        return user

    async def login(self, phone: str, password: str) -> TokenPair:
        """BR Accounts 2, 7, 8: same error for unknown phone and wrong password."""
        user = await self.users.get_by_phone(phone)
        # Hash even when the phone is unknown, so the response time doesn't reveal it.
        password_hash = user.password_hash if user else dummy_password_hash()
        password_ok = await to_thread.run_sync(verify_password, password, password_hash)
        if user is None or not password_ok:
            raise InvalidCredentialsError()
        if not user.is_active:
            raise AccountDisabledError()
        pair = self._issue_pair(user.id)
        await self.session.commit()
        return pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate: the old refresh token is revoked and a new pair issued (BR Accounts 6)."""
        claims = decode_token(refresh_token, "refresh")
        row = await self.tokens.get_by_jti_for_update(claims.jti)
        now = datetime.now(UTC)
        if (
            row is None
            or row.user_id != claims.user_id
            or row.revoked_at is not None
            or row.expires_at <= now
        ):
            raise InvalidTokenError()
        user = await self.users.get(claims.user_id)
        if user is None:
            raise InvalidTokenError()
        if not user.is_active:
            raise AccountDisabledError()
        row.revoked_at = now
        pair = self._issue_pair(user.id)
        await self.session.commit()
        return pair

    async def logout(self, user: User, refresh_token: str) -> None:
        """Revoke only the refresh token sent; the user's other sessions stay valid."""
        claims = decode_token(refresh_token, "refresh")
        row = await self.tokens.get_by_jti_for_update(claims.jti)
        if row is None or row.user_id != user.id or row.revoked_at is not None:
            raise InvalidTokenError()
        row.revoked_at = datetime.now(UTC)
        await self.session.commit()

    def _issue_pair(self, user_id: int) -> TokenPair:
        access = create_access_token(user_id)
        refresh = create_refresh_token(user_id)
        self.tokens.add(
            RefreshToken(user_id=user_id, jti=refresh.jti, expires_at=refresh.expires_at)
        )
        return TokenPair(
            access_token=access.token,
            refresh_token=refresh.token,
            expires_in=get_settings().access_token_minutes * 60,
        )
