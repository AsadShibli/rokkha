from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus, IncidentStatus, IncidentType
from app.models.incident import Incident, IncidentEvent
from app.models.officer import Officer
from app.repositories.incident_repository import IncidentRepository
from app.repositories.officer_repository import OfficerRepository


def record(
    incident: Incident,
    to_status: IncidentStatus,
    actor_id: int | None,
    *,
    note: str | None = None,
    officer_id: int | None = None,
) -> None:
    """Change status and append the matching audit event (BR Lifecycle 8)."""
    from_status = incident.status if incident.id is not None else None
    incident.status = to_status
    incident.events.append(
        IncidentEvent(
            actor_id=actor_id,
            officer_id=officer_id,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )


def release(officer: Officer | None) -> None:
    """Officer leaves an incident and is free again (BR Lifecycle 6)."""
    if officer is not None and officer.duty_status == DutyStatus.BUSY:
        officer.duty_status = DutyStatus.AVAILABLE


class DispatchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.officers = OfficerRepository(session)
        self.incidents = IncidentRepository(session)

    def assign(
        self,
        incident: Incident,
        officer: Officer,
        actor_id: int | None,
        note: str | None = None,
    ) -> None:
        """Give `officer` the incident: officer busy, incident assigned, one event.

        The caller must hold the row lock on `officer` and commit afterwards.
        """
        officer.duty_status = DutyStatus.BUSY
        incident.officer = officer
        incident.assigned_at = datetime.now(UTC)
        incident.accepted_at = None
        record(incident, IncidentStatus.ASSIGNED, actor_id, note=note, officer_id=officer.id)

    async def assign_nearest(
        self, incident: Incident, exclude_ids: Sequence[int] = (), note: str | None = None
    ) -> Officer | None:
        """System auto-assignment to the nearest reachable officer city-wide, if any."""
        officer = await self.officers.nearest_reachable_for_update(
            incident.lat, incident.lng, exclude_ids=exclude_ids
        )
        if officer is not None:
            self.assign(incident, officer, actor_id=None, note=note)
        return officer

    async def escalate(self, incident_id: int, officer_id: int) -> Incident | None:
        """SOS still not accepted by `officer_id`: hand it to the next-nearest officer.

        Returns None (nothing to do) if, meanwhile, the officer accepted, the citizen
        cancelled, or the incident was reassigned. Otherwise the officer is freed and the
        SOS goes to the nearest reachable officer who hasn't had it yet, or back to pending.
        """
        incident = await self.incidents.get_for_update(incident_id)
        if (
            incident is None
            or incident.type != IncidentType.SOS
            or incident.status != IncidentStatus.ASSIGNED
            or incident.officer_id != officer_id
        ):
            return None
        release(incident.officer)
        # Never re-offer the SOS to anyone who already had it (no ping-pong between two
        # officers); when everyone nearby has timed out it waits for the station admin.
        tried = {e.officer_id for e in incident.events if e.officer_id is not None}
        note = "Escalated: not accepted within the time limit"
        if await self.assign_nearest(incident, exclude_ids=sorted(tried), note=note) is None:
            incident.officer = None
            incident.assigned_at = None
            record(incident, IncidentStatus.PENDING, None, note=f"{note}; no other officer free")
        await self.session.commit()
        return incident
