from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ActiveSosExistsError, NoStationError
from app.db.errors import commit_or_conflict, flush_or_conflict
from app.models.enums import IncidentStatus, IncidentType
from app.models.incident import Incident
from app.models.user import User
from app.repositories.incident_repository import IncidentRepository
from app.repositories.station_repository import StationRepository
from app.schemas.incident import ReportIn, SosIn
from app.services.dispatch_service import DispatchService, record


class IncidentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.incidents = IncidentRepository(session)
        self.stations = StationRepository(session)
        self.dispatch = DispatchService(session)

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
        await self.dispatch.assign_nearest(incident)
        await commit_or_conflict(self.session)
        return incident

    async def file_report(self, citizen: User, data: ReportIn) -> Incident:
        """Non-urgent report: never auto-assigned (BR Incidents-creation 6)."""
        incident = await self._new_incident(
            citizen, IncidentType.REPORT, data.lat, data.lng, data.description
        )
        await commit_or_conflict(self.session)
        return incident

    async def _new_incident(
        self, citizen: User, type_: IncidentType, lat: float, lng: float, description: str | None
    ) -> Incident:
        station = await self.stations.nearest(lat, lng)
        if station is None:
            raise NoStationError()
        incident = Incident(
            citizen_id=citizen.id,
            station_id=station.id,
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
