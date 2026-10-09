from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ActiveSosExistsError,
    InvalidTransitionError,
    NoStationError,
    NotFoundError,
    OfficerUnavailableError,
)
from app.db.errors import commit_or_conflict, flush_or_conflict
from app.models.enums import IncidentStatus, IncidentType, UserRole
from app.models.incident import Incident
from app.models.user import User
from app.repositories.incident_repository import IncidentRepository, visibility
from app.repositories.officer_repository import OfficerRepository, is_reachable
from app.repositories.station_repository import StationRepository
from app.schemas.common import PageParams
from app.schemas.incident import IncidentOut, ReportIn, SosIn
from app.services.dispatch_service import DispatchService, record, release
from app.services.realtime import EventPublisher, NullPublisher
from app.workers.queue import JobQueue, NullJobQueue

# Which statuses each action may start from (BR Lifecycle 2). Anything else -> 409.
CAN_ACCEPT = {IncidentStatus.ASSIGNED}
CAN_RESOLVE = {IncidentStatus.EN_ROUTE}
CAN_CANCEL = {IncidentStatus.PENDING, IncidentStatus.ASSIGNED}
CAN_REASSIGN = {IncidentStatus.PENDING, IncidentStatus.ASSIGNED, IncidentStatus.EN_ROUTE}


def ensure_status(incident: Incident, allowed: set[IncidentStatus]) -> None:
    if incident.status not in allowed:
        raise InvalidTransitionError(f"Not allowed while the incident is {incident.status.value}.")


class IncidentService:
    def __init__(
        self,
        session: AsyncSession,
        publisher: EventPublisher | None = None,
        queue: JobQueue | None = None,
    ):
        self.session = session
        self.publisher = publisher or NullPublisher()
        self.queue = queue or NullJobQueue()
        self.incidents = IncidentRepository(session)
        self.stations = StationRepository(session)
        self.officers = OfficerRepository(session)
        self.dispatch = DispatchService(session)

    # --- creation ------------------------------------------------------------------------

    async def raise_sos(self, citizen: User, data: SosIn) -> Incident:
        """Create an SOS and auto-assign the nearest reachable officer in ONE transaction.

        No free officer is not an error: the SOS stays pending for the station to assign.
        """
        if await self.incidents.has_open_sos(citizen.id):
            raise ActiveSosExistsError()
        incident = await self._new_incident(
            citizen, IncidentType.SOS, data.lat, data.lng, data.description
        )
        # INSERT now: a racing second SOS from the same citizen fails here on the partial
        # unique index (-> 409 ACTIVE_SOS_EXISTS) before any officer gets locked.
        await flush_or_conflict(self.session)
        officer = await self.dispatch.assign_nearest(incident)
        await commit_or_conflict(self.session)
        if officer is not None:
            await self.queue.schedule_escalation(incident.id, officer.id)
        return incident

    async def file_report(self, citizen: User, data: ReportIn) -> Incident:
        """Non-urgent report: never auto-assigned (BR Incidents-creation 6)."""
        incident = await self._new_incident(
            citizen, IncidentType.REPORT, data.lat, data.lng, data.description
        )
        await commit_or_conflict(self.session)
        return incident

    # --- reading -------------------------------------------------------------------------

    async def get_visible(self, user: User, incident_id: int) -> Incident:
        scope = visibility(user, await self._officer_id(user))
        incident = await self.incidents.get_with_events(incident_id, scope)
        if incident is None:
            raise NotFoundError("Incident not found.")
        return incident

    async def list_visible(
        self,
        user: User,
        params: PageParams,
        *,
        status: IncidentStatus | None,
        type_: IncidentType | None,
        station_id: int | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[Sequence[Incident], int]:
        if user.role != UserRole.SUPER_ADMIN:
            station_id = None  # the filter is super-admin only; others are scoped anyway
        return await self.incidents.list(
            params,
            visibility(user, await self._officer_id(user)),
            status=status,
            type_=type_,
            station_id=station_id,
            date_from=date_from,
            date_to=date_to,
        )

    # --- lifecycle -----------------------------------------------------------------------

    async def accept(self, user: User, incident_id: int, note: str | None) -> Incident:
        """assigned -> en_route, by the currently assigned officer only."""
        incident = await self._locked_for_officer(user, incident_id)
        ensure_status(incident, CAN_ACCEPT)
        incident.accepted_at = datetime.now(UTC)
        record(incident, IncidentStatus.EN_ROUTE, user.id, note=note)
        await commit_or_conflict(self.session)
        await self.publish_status(incident)
        return incident

    async def resolve(self, user: User, incident_id: int, note: str | None) -> Incident:
        """en_route -> resolved; the officer is free again."""
        incident = await self._locked_for_officer(user, incident_id)
        ensure_status(incident, CAN_RESOLVE)
        incident.resolved_at = datetime.now(UTC)
        record(incident, IncidentStatus.RESOLVED, user.id, note=note)
        release(incident.officer)
        await commit_or_conflict(self.session)
        await self.publish_status(incident)
        return incident

    async def cancel(self, citizen: User, incident_id: int, note: str | None) -> Incident:
        """pending|assigned -> cancelled, by the owner; not once the officer is en route."""
        incident = await self.incidents.get_for_update(incident_id)
        if incident is None or incident.citizen_id != citizen.id:
            raise NotFoundError("Incident not found.")
        ensure_status(incident, CAN_CANCEL)
        incident.cancelled_at = datetime.now(UTC)
        record(incident, IncidentStatus.CANCELLED, citizen.id, note=note)
        release(incident.officer)
        await commit_or_conflict(self.session)
        await self.publish_status(incident)
        return incident

    async def reassign(
        self, admin: User, incident_id: int, officer_id: int, note: str | None
    ) -> Incident:
        """Station admin (re)assigns an open incident to a reachable officer of their station."""
        incident = await self.incidents.get_for_update(incident_id)
        if incident is None or incident.station_id != admin.station_id:
            raise NotFoundError("Incident not found.")
        ensure_status(incident, CAN_REASSIGN)
        if officer_id == incident.officer_id:
            raise OfficerUnavailableError("The incident is already assigned to that officer.")
        # Lock order: incident first, then officer (same as every other path) -> no deadlock.
        target = await self.officers.get_for_update(officer_id)
        if target is None or target.station_id != admin.station_id or not is_reachable(target):
            raise OfficerUnavailableError()
        release(incident.officer)
        self.dispatch.assign(incident, target, actor_id=admin.id, note=note)
        await commit_or_conflict(self.session)
        await self.publish_status(incident)
        if incident.type == IncidentType.SOS:
            await self.queue.schedule_escalation(incident.id, target.id)
        return incident

    # --- helpers -------------------------------------------------------------------------

    async def publish_status(self, incident: Incident) -> None:
        """Push the new state to live subscribers (after commit, so it's real)."""
        payload = IncidentOut.from_incident(incident).model_dump(mode="json")
        await self.publisher.publish(incident.id, {"type": "status", "incident": payload})

    async def _locked_for_officer(self, user: User, incident_id: int) -> Incident:
        officer_id = await self._officer_id(user)
        incident = await self.incidents.get_for_update(incident_id)
        if incident is None or officer_id is None or incident.officer_id != officer_id:
            raise NotFoundError("Incident not found.")
        return incident

    async def _officer_id(self, user: User) -> int | None:
        if user.role != UserRole.OFFICER:
            return None
        officer = await self.officers.get_by_user_id(user.id)
        return officer.id if officer else None

    async def _new_incident(
        self, citizen: User, type_: IncidentType, lat: float, lng: float, description: str | None
    ) -> Incident:
        station = await self.stations.nearest(lat, lng)
        if station is None:
            raise NoStationError()
        incident = Incident(
            citizen_id=citizen.id,
            station=station,
            type=type_,
            status=IncidentStatus.PENDING,
            lat=lat,
            lng=lng,
            description=description,
            events=[],
        )
        # Creation is the first event (from_status = NULL).
        record(incident, IncidentStatus.PENDING, citizen.id)
        self.incidents.add(incident)
        return incident
