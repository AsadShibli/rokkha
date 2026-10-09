import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_jti_for_update(self, jti: uuid.UUID) -> RefreshToken | None:
        """Row-locked, so two refreshes with the same token can't both succeed."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti).with_for_update()
        return await self.session.scalar(stmt)

    def add(self, token: RefreshToken) -> None:
        self.session.add(token)
