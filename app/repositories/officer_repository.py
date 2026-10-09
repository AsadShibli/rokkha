from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus
from app.models.officer import Officer
from app.repositories.base import paginate
from app.schemas.common import PageParams


class OfficerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int, *, for_update: bool = False) -> Officer | None:
        stmt = select(Officer).where(Officer.user_id == user_id)
        if for_update:
            # Lock only the officer row (not the joined user row): dispatch locks the same row.
            stmt = stmt.with_for_update(of=Officer)
        return await self.session.scalar(stmt)

    async def exists_badge(self, badge_no: str) -> bool:
        stmt = select(Officer.id).where(Officer.badge_no == badge_no)
        return await self.session.scalar(stmt) is not None

    async def list(
        self,
        params: PageParams,
        station_id: int | None = None,
        duty_status: DutyStatus | None = None,
    ) -> tuple[Sequence[Officer], int]:
        stmt = select(Officer).order_by(Officer.created_at.desc(), Officer.id.desc())
        if station_id is not None:
            stmt = stmt.where(Officer.station_id == station_id)
        if duty_status is not None:
            stmt = stmt.where(Officer.duty_status == duty_status)
        return await paginate(self.session, stmt, params)

    def add(self, officer: Officer) -> None:
        self.session.add(officer)
