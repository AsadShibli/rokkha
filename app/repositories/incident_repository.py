from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import ColumnElement, exists, false, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import OPEN_INCIDENT_STATUSES, IncidentStatus, IncidentType, UserRole
from app.models.incident import Incident, IncidentEvent
from app.models.user import User
from app.repositories.base import paginate
from app.schemas.common import PageParams


def visibility(user: User, officer_id: int | None) -> ColumnElement[bool]:
    """Which incidents a user may see (BR Roles 1-4). Anything else behaves as 404."""
    if user.role == UserRole.SUPER_ADMIN:
        return true()
    if user.role == UserRole.STATION_ADMIN:
        return Incident.station_id == user.station_id
    if user.role == UserRole.OFFICER:
        if officer_id is None:
            return false()
        # Currently assigned, or assigned at some point (recorded on the assignment event).
        previously = exists().where(
            IncidentEvent.incident_id == Incident.id, IncidentEvent.officer_id == officer_id
        )
        return (Incident.officer_id == officer_id) | previously
    return Incident.citizen_id == user.id


class IncidentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, incident: Incident) -> None:
        self.session.add(incident)

    async def has_open_sos(self, citizen_id: int) -> bool:
        stmt = select(Incident.id).where(
            Incident.citizen_id == citizen_id,
            Incident.type == IncidentType.SOS,
            Incident.status.in_(OPEN_INCIDENT_STATUSES),
        )
        return await self.session.scalar(stmt.limit(1)) is not None

    async def get_with_events(
        self, incident_id: int, scope: ColumnElement[bool] | None = None
    ) -> Incident | None:
        stmt = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(selectinload(Incident.events))
        )
        if scope is not None:
            stmt = stmt.where(scope)
        return await self.session.scalar(stmt)

    async def get_for_update(self, incident_id: int) -> Incident | None:
        """Row-locked incident (with its events) for a status change."""
        stmt = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(selectinload(Incident.events))
            .with_for_update(of=Incident)
        )
        return await self.session.scalar(stmt)

    async def list(
        self,
        params: PageParams,
        scope: ColumnElement[bool],
        *,
        status: IncidentStatus | None = None,
        type_: IncidentType | None = None,
        station_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[Sequence[Incident], int]:
        # Scope first; filters can only narrow it, never widen it.
        stmt = select(Incident).where(scope)
        if status is not None:
            stmt = stmt.where(Incident.status == status)
        if type_ is not None:
            stmt = stmt.where(Incident.type == type_)
        if station_id is not None:
            stmt = stmt.where(Incident.station_id == station_id)
        if date_from is not None:
            stmt = stmt.where(Incident.created_at >= start_of(date_from))
        if date_to is not None:
            stmt = stmt.where(Incident.created_at < start_of(date_to + timedelta(days=1)))
        stmt = stmt.order_by(Incident.created_at.desc(), Incident.id.desc())
        return await paginate(self.session, stmt, params)


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)
