from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GdCategory, GdStatus, UserRole
from app.models.gd import Gd, GdSequence
from app.models.user import User
from app.repositories.base import paginate
from app.repositories.incident_repository import start_of
from app.schemas.common import PageParams


def gd_visibility(user: User) -> ColumnElement[bool]:
    """Citizen: own GDs; station admin: own station; super admin: all."""
    if user.role == UserRole.SUPER_ADMIN:
        return true()
    if user.role == UserRole.STATION_ADMIN:
        return Gd.station_id == user.station_id
    return Gd.citizen_id == user.id


class GdRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, gd: Gd) -> None:
        self.session.add(gd)

    async def next_number(self, station_id: int, year: int) -> int:
        """Atomically take the next sequence value for (station, year).

        The upsert row-locks the counter until the transaction ends, so two parallel GDs get
        different numbers; the first GD of a new year starts at 1; a rolled-back GD gives
        its number back.
        """
        stmt = (
            insert(GdSequence)
            .values(station_id=station_id, year=year, last_value=1)
            .on_conflict_do_update(
                index_elements=[GdSequence.station_id, GdSequence.year],
                set_={"last_value": GdSequence.last_value + 1},
            )
            .returning(GdSequence.last_value)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def get_by_number(
        self, gd_number: str, scope: ColumnElement[bool], *, for_update: bool = False
    ) -> Gd | None:
        stmt = select(Gd).where(Gd.gd_number == gd_number, scope)
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def list(
        self,
        params: PageParams,
        scope: ColumnElement[bool],
        *,
        status: GdStatus | None = None,
        category: GdCategory | None = None,
        station_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[Sequence[Gd], int]:
        stmt = select(Gd).where(scope)
        if status is not None:
            stmt = stmt.where(Gd.status == status)
        if category is not None:
            stmt = stmt.where(Gd.category == category)
        if station_id is not None:
            stmt = stmt.where(Gd.station_id == station_id)
        if date_from is not None:
            stmt = stmt.where(Gd.created_at >= start_of(date_from))
        if date_to is not None:
            stmt = stmt.where(Gd.created_at < start_of(date_to + timedelta(days=1)))
        stmt = stmt.order_by(Gd.created_at.desc(), Gd.id.desc())
        return await paginate(self.session, stmt, params)
