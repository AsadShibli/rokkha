from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IncidentStatus, IncidentType
from app.models.incident import Incident
from app.models.officer import Officer
from app.schemas.common import Latitude, Longitude


class SosIn(BaseModel):
    lat: Latitude
    lng: Longitude
    description: str | None = Field(default=None, max_length=1000)


class ReportIn(BaseModel):
    lat: Latitude
    lng: Longitude
    description: str = Field(min_length=10, max_length=1000)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ReassignIn(NoteIn):
    officer_id: int


class OfficerBrief(BaseModel):
    """What the citizen and staff see about the handling officer."""

    id: int
    name: str
    rank: str
    phone: str
    last_lat: float | None
    last_lng: float | None

    @classmethod
    def from_officer(cls, officer: Officer) -> "OfficerBrief":
        return cls(
            id=officer.id,
            name=officer.user.name,
            rank=officer.rank,
            phone=officer.user.phone,
            last_lat=officer.last_lat,
            last_lng=officer.last_lng,
        )


class IncidentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    actor_id: int | None
    officer_id: int | None
    note: str | None
    created_at: datetime


class IncidentOut(BaseModel):
    id: int
    type: IncidentType
    status: IncidentStatus
    lat: float
    lng: float
    description: str | None
    station_id: int
    citizen_id: int
    officer: OfficerBrief | None
    created_at: datetime
    assigned_at: datetime | None
    accepted_at: datetime | None
    resolved_at: datetime | None
    cancelled_at: datetime | None

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentOut":
        return cls(
            id=incident.id,
            type=incident.type,
            status=incident.status,
            lat=incident.lat,
            lng=incident.lng,
            description=incident.description,
            station_id=incident.station_id,
            citizen_id=incident.citizen_id,
            officer=OfficerBrief.from_officer(incident.officer) if incident.officer else None,
            created_at=incident.created_at,
            assigned_at=incident.assigned_at,
            accepted_at=incident.accepted_at,
            resolved_at=incident.resolved_at,
            cancelled_at=incident.cancelled_at,
        )


class IncidentDetail(IncidentOut):
    events: list[IncidentEventOut]

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentDetail":
        base = IncidentOut.from_incident(incident).model_dump()
        events = [IncidentEventOut.model_validate(e) for e in incident.events]
        return cls(**base, events=events)
