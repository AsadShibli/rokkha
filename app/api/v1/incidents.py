from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Citizen, CurrentUser, DbSession, OfficerUser, Publisher, StationAdmin
from app.models.enums import IncidentStatus, IncidentType
from app.schemas.common import Page, PageParams, page_params
from app.schemas.errors import ErrorResponse
from app.schemas.incident import (
    IncidentDetail,
    IncidentOut,
    NoteIn,
    ReassignIn,
    ReportIn,
    SosIn,
)
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])

AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Role not allowed"},
}
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Not found or not yours"}}
TRANSITION = {409: {"model": ErrorResponse, "description": "Not allowed from current status"}}


@router.post(
    "/sos",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Raise an SOS; the nearest reachable officer is assigned automatically",
    description="Returns `assigned` with the officer, or `pending` if no officer is free.",
    responses={
        **AUTH_ERRORS,
        409: {"model": ErrorResponse, "description": "You already have an open SOS"},
    },
)
async def raise_sos(data: SosIn, citizen: Citizen, db: DbSession) -> IncidentDetail:
    incident = await IncidentService(db).raise_sos(citizen, data)
    return IncidentDetail.from_incident(incident)


@router.post(
    "/report",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="File a non-urgent report (stays pending until a station admin assigns it)",
    responses=AUTH_ERRORS,
)
async def file_report(data: ReportIn, citizen: Citizen, db: DbSession) -> IncidentDetail:
    incident = await IncidentService(db).file_report(citizen, data)
    return IncidentDetail.from_incident(incident)


@router.get(
    "",
    response_model=Page[IncidentOut],
    summary="List incidents you may see (citizen: own; officer: assigned; admin: station)",
    responses=AUTH_ERRORS,
)
async def list_incidents(
    user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    type_: Annotated[IncidentType | None, Query(alias="type")] = None,
    date_from: Annotated[date | None, Query(alias="from", description="Created on/after")] = None,
    date_to: Annotated[date | None, Query(alias="to", description="Created on/before")] = None,
    station_id: Annotated[int | None, Query(description="Super admin only")] = None,
) -> Page[IncidentOut]:
    items, total = await IncidentService(db).list_visible(
        user,
        params,
        status=status_,
        type_=type_,
        station_id=station_id,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(
        items=[IncidentOut.from_incident(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetail,
    summary="One incident with its full status timeline",
    responses={**AUTH_ERRORS, **NOT_FOUND},
)
async def get_incident(incident_id: int, user: CurrentUser, db: DbSession) -> IncidentDetail:
    incident = await IncidentService(db).get_visible(user, incident_id)
    return IncidentDetail.from_incident(incident)


@router.post(
    "/{incident_id}/accept",
    response_model=IncidentDetail,
    summary="Assigned officer accepts (assigned -> en_route)",
    responses={**AUTH_ERRORS, **NOT_FOUND, **TRANSITION},
)
async def accept(
    incident_id: int,
    user: OfficerUser,
    db: DbSession,
    publisher: Publisher,
    data: NoteIn | None = None,
) -> IncidentDetail:
    note = data.note if data else None
    incident = await IncidentService(db, publisher).accept(user, incident_id, note)
    return IncidentDetail.from_incident(incident)


@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentDetail,
    summary="Assigned officer resolves (en_route -> resolved)",
    responses={**AUTH_ERRORS, **NOT_FOUND, **TRANSITION},
)
async def resolve(
    incident_id: int,
    user: OfficerUser,
    db: DbSession,
    publisher: Publisher,
    data: NoteIn | None = None,
) -> IncidentDetail:
    note = data.note if data else None
    incident = await IncidentService(db, publisher).resolve(user, incident_id, note)
    return IncidentDetail.from_incident(incident)


@router.post(
    "/{incident_id}/cancel",
    response_model=IncidentDetail,
    summary="Owner cancels (only before the officer is en route)",
    responses={**AUTH_ERRORS, **NOT_FOUND, **TRANSITION},
)
async def cancel(
    incident_id: int,
    citizen: Citizen,
    db: DbSession,
    publisher: Publisher,
    data: NoteIn | None = None,
) -> IncidentDetail:
    note = data.note if data else None
    incident = await IncidentService(db, publisher).cancel(citizen, incident_id, note)
    return IncidentDetail.from_incident(incident)


@router.post(
    "/{incident_id}/reassign",
    response_model=IncidentDetail,
    summary="Station admin assigns or reassigns to a reachable officer of the station",
    responses={
        **AUTH_ERRORS,
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Invalid transition or officer unavailable"},
    },
)
async def reassign(
    incident_id: int, data: ReassignIn, admin: StationAdmin, db: DbSession, publisher: Publisher
) -> IncidentDetail:
    incident = await IncidentService(db, publisher).reassign(
        admin, incident_id, data.officer_id, data.note
    )
    return IncidentDetail.from_incident(incident)
