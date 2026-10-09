from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus, IncidentStatus, IncidentType, UserRole
from app.models.incident import Incident
from tests.factories import auth, make_officer, make_station, make_user


async def add_incident(db: AsyncSession, station, citizen, officer=None, **fields) -> Incident:
    incident = Incident(
        citizen_id=citizen.id,
        station_id=station.id,
        officer_id=officer.id if officer else None,
        type=fields.pop("type", IncidentType.SOS),
        lat=24.89,
        lng=91.86,
        **fields,
    )
    db.add(incident)
    await db.flush()
    return incident


async def test_station_admin_sees_own_station_counts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot = await make_station(db_session, code="KOT")
    jal = await make_station(db_session, code="JAL", lat=24.95)
    admin = await make_user(db_session, UserRole.STATION_ADMIN, station=kot)
    citizen = await make_user(db_session)
    busy = await make_officer(db_session, kot, DutyStatus.BUSY)
    await make_officer(db_session, kot, DutyStatus.AVAILABLE)
    await make_officer(db_session, jal, DutyStatus.AVAILABLE)

    now = datetime.now(UTC)
    await add_incident(
        db_session,
        kot,
        citizen,
        busy,
        status=IncidentStatus.EN_ROUTE,
        created_at=now - timedelta(minutes=10),
        accepted_at=now - timedelta(minutes=5),
    )
    await add_incident(
        db_session,
        kot,
        await make_user(db_session),
        status=IncidentStatus.PENDING,
        type=IncidentType.REPORT,
    )
    await add_incident(db_session, jal, await make_user(db_session), status=IncidentStatus.PENDING)

    # A station admin asking for another station still gets their own.
    response = await client.get(f"/dashboard/stats?station_id={jal.id}", headers=auth(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["station_id"] == kot.id
    assert body["incidents"] == {
        "pending": 1,
        "assigned": 0,
        "en_route": 1,
        "resolved": 0,
        "cancelled": 0,
    }
    assert body["open_sos"] == 1
    assert body["officers"] == {"off_duty": 0, "available": 1, "busy": 1}
    assert body["gds"]["submitted"] == 0
    assert body["avg_response_seconds_7d"] == 300


async def test_super_admin_city_wide_and_empty_average(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot = await make_station(db_session, code="KOT")
    super_admin = await make_user(db_session, UserRole.SUPER_ADMIN)
    await add_incident(db_session, kot, await make_user(db_session), status=IncidentStatus.PENDING)

    body = (await client.get("/dashboard/stats", headers=auth(super_admin))).json()

    assert body["station_id"] is None
    assert body["incidents"]["pending"] == 1
    assert body["avg_response_seconds_7d"] is None


async def test_citizen_cannot_see_dashboard(client: AsyncClient, db_session: AsyncSession) -> None:
    citizen = await make_user(db_session)

    assert (await client.get("/dashboard/stats", headers=auth(citizen))).status_code == 403
