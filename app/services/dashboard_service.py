from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import ColumnElement, extract, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    OPEN_INCIDENT_STATUSES,
    DutyStatus,
    GdStatus,
    IncidentStatus,
    IncidentType,
    UserRole,
)
from app.models.gd import Gd
from app.models.incident import Incident
from app.models.officer import Officer
from app.models.user import User
from app.schemas.dashboard import DashboardOut

RESPONSE_WINDOW = timedelta(days=7)


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def stats(self, user: User, station_id: int | None) -> DashboardOut:
        # BR Dashboard 1: station admins always get their own station.
        if user.role == UserRole.STATION_ADMIN:
            station_id = user.station_id

        def at(column) -> ColumnElement[bool]:
            return column == station_id if station_id is not None else true()

        incidents = await self._count_by(Incident.status, IncidentStatus, at(Incident.station_id))
        gds = await self._count_by(Gd.status, GdStatus, at(Gd.station_id))
        officers = await self._count_by(Officer.duty_status, DutyStatus, at(Officer.station_id))

        open_sos = await self.session.scalar(
            select(func.count()).where(
                at(Incident.station_id),
                Incident.type == IncidentType.SOS,
                Incident.status.in_(OPEN_INCIDENT_STATUSES),
            )
        )
        # Response time = accepted_at - created_at, over incidents accepted in the last 7 days.
        avg_seconds = await self.session.scalar(
            select(func.avg(extract("epoch", Incident.accepted_at - Incident.created_at))).where(
                at(Incident.station_id),
                Incident.accepted_at >= datetime.now(UTC) - RESPONSE_WINDOW,
            )
        )
        return DashboardOut(
            station_id=station_id,
            incidents=incidents,
            open_sos=open_sos or 0,
            gds=gds,
            officers=officers,
            avg_response_seconds_7d=round(float(avg_seconds)) if avg_seconds is not None else None,
        )

    async def _count_by(
        self, column, enum: type[StrEnum], where: ColumnElement[bool]
    ) -> dict[str, int]:
        rows = await self.session.execute(
            select(column, func.count()).where(where).group_by(column)
        )
        counts = {member.value: 0 for member in enum}  # zero-fill so every key is present
        counts.update({str(status): n for status, n in rows.all()})
        return counts
