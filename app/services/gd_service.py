from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.core.time import local_now
from app.db.errors import commit_or_conflict
from app.models.enums import GdCategory, GdStatus, UserRole
from app.models.gd import Gd
from app.models.user import User
from app.repositories.gd_repository import GdRepository, gd_visibility
from app.repositories.station_repository import StationRepository
from app.schemas.common import PageParams
from app.schemas.gd import GdCreate, GdReviewIn

# action -> (allowed from, resulting status) (BR Online GD 5)
REVIEW_TRANSITIONS: dict[str, tuple[GdStatus, GdStatus]] = {
    "start_review": (GdStatus.SUBMITTED, GdStatus.UNDER_REVIEW),
    "approve": (GdStatus.UNDER_REVIEW, GdStatus.APPROVED),
    "reject": (GdStatus.UNDER_REVIEW, GdStatus.REJECTED),
}


class GdService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.gds = GdRepository(session)
        self.stations = StationRepository(session)

    async def file(self, citizen: User, data: GdCreate) -> Gd:
        """Number + insert in one transaction: e.g. SYL-KOT-2026-000123 (BR Online GD 3-4)."""
        station = await self.stations.get(data.station_id)
        if station is None:
            raise ValidationFailedError(
                details=[{"field": "station_id", "message": "Station does not exist"}]
            )
        year = local_now().year
        seq = await self.gds.next_number(station.id, year)
        gd = Gd(
            gd_number=f"{station.city_code}-{station.code}-{year}-{seq:06d}",
            citizen_id=citizen.id,
            station=station,
            category=data.category,
            title=data.title,
            details=data.details,
            incident_date=data.incident_date,
            status=GdStatus.SUBMITTED,
        )
        self.gds.add(gd)
        await commit_or_conflict(self.session)
        return gd

    async def get_visible(self, user: User, gd_number: str) -> Gd:
        gd = await self.gds.get_by_number(gd_number, gd_visibility(user))
        if gd is None:
            raise NotFoundError("GD not found.")
        return gd

    async def list_visible(
        self,
        user: User,
        params: PageParams,
        *,
        status: GdStatus | None,
        category: GdCategory | None,
        station_id: int | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[Sequence[Gd], int]:
        if user.role != UserRole.SUPER_ADMIN:
            station_id = None
        return await self.gds.list(
            params,
            gd_visibility(user),
            status=status,
            category=category,
            station_id=station_id,
            date_from=date_from,
            date_to=date_to,
        )

    async def review(self, admin: User, gd_number: str, data: GdReviewIn) -> Gd:
        """Station admin of the GD's station moves it through review (BR Online GD 5-7)."""
        gd = await self.gds.get_by_number(gd_number, gd_visibility(admin), for_update=True)
        if gd is None:
            raise NotFoundError("GD not found.")
        allowed_from, to_status = REVIEW_TRANSITIONS[data.action]
        if gd.status != allowed_from:
            raise InvalidTransitionError(f"Cannot {data.action} a GD that is {gd.status.value}.")
        gd.status = to_status
        if to_status in (GdStatus.APPROVED, GdStatus.REJECTED):
            gd.reviewed_by = admin.id
            gd.reviewed_at = datetime.now(UTC)
            gd.review_note = data.note
        await commit_or_conflict(self.session)
        return gd
