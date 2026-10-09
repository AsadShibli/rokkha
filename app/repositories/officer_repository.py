from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import DutyStatus
from app.models.officer import Officer
from app.repositories.base import paginate
from app.schemas.common import PageParams
from app.services.geo import haversine_km


class OfficerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int, *, for_update: bool = False) -> Officer | None:
        stmt = select(Officer).where(Officer.user_id == user_id)
        if for_update:
            # Lock only the officer row (not the joined user row): dispatch locks the same row.
            stmt = stmt.with_for_update(of=Officer)
        return await self.session.scalar(stmt)

    async def get_for_update(self, officer_id: int) -> Officer | None:
        stmt = select(Officer).where(Officer.id == officer_id).with_for_update(of=Officer)
        return await self.session.scalar(stmt)

    async def nearest_reachable_for_update(
        self,
        lat: float,
        lng: float,
        *,
        station_id: int | None = None,
        exclude_ids: Sequence[int] = (),
    ) -> Officer | None:
        """Nearest reachable officer, row-locked (BR Incidents-creation 3-4).

        FOR UPDATE SKIP LOCKED: if a parallel SOS has already locked the nearest officer, this
        query skips that row and takes the next one instead of waiting, so two simultaneous
        SOS calls can never be given the same officer.
        """
        stmt = (
            select(Officer)
            .where(*reachable_filters())
            .order_by(haversine_km(Officer.last_lat, Officer.last_lng, lat, lng), Officer.id)
            .limit(1)
            .with_for_update(of=Officer, skip_locked=True)
        )
        if station_id is not None:
            stmt = stmt.where(Officer.station_id == station_id)
        if exclude_ids:
            stmt = stmt.where(Officer.id.not_in(exclude_ids))
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


def reachable_filters() -> list:
    """BR Officers 8: available, has a location, seen within the reachability window."""
    window = timedelta(minutes=get_settings().officer_reachable_minutes)
    return [
        Officer.duty_status == DutyStatus.AVAILABLE,
        Officer.last_lat.is_not(None),
        Officer.last_seen_at >= datetime.now(UTC) - window,
    ]


def is_reachable(officer: Officer) -> bool:
    window = timedelta(minutes=get_settings().officer_reachable_minutes)
    return (
        officer.duty_status == DutyStatus.AVAILABLE
        and officer.last_lat is not None
        and officer.last_seen_at is not None
        and officer.last_seen_at >= datetime.now(UTC) - window
    )
