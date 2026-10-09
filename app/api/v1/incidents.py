from fastapi import APIRouter, status

from app.api.deps import Citizen, DbSession
from app.schemas.errors import ErrorResponse
from app.schemas.incident import IncidentDetail, ReportIn, SosIn
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])

AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Role not allowed"},
}


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
