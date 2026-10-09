from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, OfficerBusyError
from app.db.errors import commit_or_conflict, taken
from app.models.enums import DutyStatus, UserRole
from app.models.officer import Officer
from app.models.user import User
from app.repositories.incident_repository import IncidentRepository
from app.repositories.officer_repository import OfficerRepository
from app.schemas.common import PageParams
from app.schemas.officer import OfficerCreate
from app.services.realtime import EventPublisher, NullPublisher
from app.services.user_service import UserService


class OfficerService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = publisher or NullPublisher()
        self.officers = OfficerRepository(session)
        self.accounts = UserService(session)

    async def list(
        self,
        caller: User,
        params: PageParams,
        station_id: int | None,
        duty_status: DutyStatus | None,
    ) -> tuple[Sequence[Officer], int]:
        # BR Roles 3: a station admin only ever sees their own station.
        if caller.role == UserRole.STATION_ADMIN:
            station_id = caller.station_id
        return await self.officers.list(params, station_id, duty_status)

    async def create(self, admin: User, data: OfficerCreate) -> Officer:
        """BR Officers 1-4: account + profile in one transaction, in the admin's station."""
        clashes = await self.accounts.taken_fields(data.phone, data.email)
        if await self.officers.exists_badge(data.badge_no):
            clashes.append(taken("badge_no"))
        if clashes:
            raise ConflictError(details=clashes)

        user = await self.accounts.build_account(data, UserRole.OFFICER)
        officer = Officer(
            user=user,
            station_id=admin.station_id,
            badge_no=data.badge_no,
            rank=data.rank,
            duty_status=DutyStatus.OFF_DUTY,
        )
        self.officers.add(officer)
        # One commit for both rows: if the officer insert fails, the user is rolled back too.
        await commit_or_conflict(self.session)
        return officer

    async def set_duty_status(self, user: User, duty_status: DutyStatus) -> Officer:
        """BR Officers 5-6: officers toggle available/off_duty; never while busy."""
        officer = await self._own_profile(user, for_update=True)
        if officer.duty_status == DutyStatus.BUSY:
            raise OfficerBusyError()
        officer.duty_status = duty_status
        await self.session.commit()
        return officer

    async def update_location(self, user: User, lat: float, lng: float) -> None:
        """BR Officers 7: every location update also refreshes last_seen_at."""
        officer = await self._own_profile(user, for_update=True)
        officer.last_lat = lat
        officer.last_lng = lng
        officer.last_seen_at = datetime.now(UTC)
        await self.session.commit()
        incident_id = await IncidentRepository(self.session).active_for_officer(officer.id)
        if incident_id is not None:
            await self.publisher.publish(
                incident_id,
                {
                    "type": "location",
                    "incident_id": incident_id,
                    "officer_id": officer.id,
                    "lat": lat,
                    "lng": lng,
                },
            )

    async def own_profile(self, user: User) -> Officer:
        return await self._own_profile(user)

    async def _own_profile(self, user: User, *, for_update: bool = False) -> Officer:
        officer = await self.officers.get_by_user_id(user.id, for_update=for_update)
        if officer is None:
            raise NotFoundError("Officer profile not found.")
        return officer
