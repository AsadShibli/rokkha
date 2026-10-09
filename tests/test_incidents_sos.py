import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus, IncidentStatus, IncidentType, UserRole
from app.models.incident import Incident
from app.repositories.incident_repository import IncidentRepository
from tests.factories import auth, make_officer, make_station, make_user

# Sylhet: Kotwali station in the centre, Jalalabad ~4 km north.
KOTWALI = {"lat": 24.8949, "lng": 91.8687}
JALALABAD = {"lat": 24.93, "lng": 91.87}
SOS_AT_KOTWALI = {**KOTWALI, "description": "Snatching near Zindabazar"}


async def setup_stations(db: AsyncSession):
    kot = await make_station(db, code="KOT", **KOTWALI)
    jal = await make_station(db, code="JAL", **JALALABAD)
    return kot, jal


async def sos(client: AsyncClient, user, body=SOS_AT_KOTWALI):
    return await client.post("/incidents/sos", json=body, headers=auth(user))


async def test_sos_assigns_nearest_reachable_officer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot, jal = await setup_stations(db_session)
    citizen = await make_user(db_session)
    far = await make_officer(db_session, jal, DutyStatus.AVAILABLE, located=True, **JALALABAD)
    near = await make_officer(
        db_session, kot, DutyStatus.AVAILABLE, located=True, lat=24.896, lng=91.869
    )

    response = await sos(client, citizen)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "assigned"
    assert body["station_id"] == kot.id
    assert body["officer"]["id"] == near.id
    assert body["assigned_at"] is not None
    assert [(e["from_status"], e["to_status"]) for e in body["events"]] == [
        (None, "pending"),
        ("pending", "assigned"),
    ]
    assert body["events"][0]["actor_id"] == citizen.id
    assert body["events"][1]["actor_id"] is None  # the system assigned it
    assert body["events"][1]["officer_id"] == near.id
    await db_session.refresh(near)
    await db_session.refresh(far)
    assert near.duty_status == DutyStatus.BUSY
    assert far.duty_status == DutyStatus.AVAILABLE


async def test_nearest_officer_can_be_from_another_station(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot, jal = await setup_stations(db_session)
    citizen = await make_user(db_session)
    jal_officer = await make_officer(
        db_session, jal, DutyStatus.AVAILABLE, located=True, lat=24.895, lng=91.8688
    )

    body = (await sos(client, citizen)).json()

    assert body["station_id"] == kot.id  # jurisdiction = nearest station
    assert body["officer"]["id"] == jal_officer.id  # officer search is city-wide


@pytest.mark.parametrize(
    "officer_kwargs",
    [
        {"duty_status": DutyStatus.OFF_DUTY, "located": True},
        {"duty_status": DutyStatus.BUSY, "located": True},
        {"duty_status": DutyStatus.AVAILABLE, "located": False},
        {"duty_status": DutyStatus.AVAILABLE, "located": True, "seen_minutes_ago": 11},
    ],
    ids=["off_duty", "busy", "no_location", "stale_location"],
)
async def test_unreachable_officers_are_skipped(
    client: AsyncClient, db_session: AsyncSession, officer_kwargs: dict
) -> None:
    kot, _ = await setup_stations(db_session)
    citizen = await make_user(db_session)
    await make_officer(db_session, kot, **officer_kwargs)

    response = await sos(client, citizen)

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["officer"] is None


async def test_second_open_sos_is_409(client: AsyncClient, db_session: AsyncSession) -> None:
    await setup_stations(db_session)
    citizen = await make_user(db_session)
    await sos(client, citizen)

    response = await sos(client, citizen)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVE_SOS_EXISTS"


async def test_db_index_blocks_second_sos_that_races_the_check(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await setup_stations(db_session)
    citizen = await make_user(db_session)
    await sos(client, citizen)

    async def no_open_sos(self, citizen_id: int) -> bool:
        return False

    monkeypatch.setattr(IncidentRepository, "has_open_sos", no_open_sos)
    response = await sos(client, citizen)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVE_SOS_EXISTS"


async def test_open_report_does_not_block_sos(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await setup_stations(db_session)
    citizen = await make_user(db_session)
    await client.post(
        "/incidents/report",
        json={**KOTWALI, "description": "Broken street light for a week"},
        headers=auth(citizen),
    )

    assert (await sos(client, citizen)).status_code == 201


@pytest.mark.parametrize("role", [UserRole.OFFICER, UserRole.SUPER_ADMIN])
async def test_only_citizens_raise_sos(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await setup_stations(db_session)
    user = await make_user(db_session, role)

    assert (await sos(client, user)).status_code == 403


async def test_sos_outside_bangladesh_is_422(client: AsyncClient, db_session: AsyncSession) -> None:
    citizen = await make_user(db_session)

    response = await sos(client, citizen, {"lat": 40.7, "lng": -74.0})

    assert response.status_code == 422


async def test_sos_without_any_station_is_503(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    citizen = await make_user(db_session)

    response = await sos(client, citizen)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NO_STATION"


async def test_report_is_never_auto_assigned(client: AsyncClient, db_session: AsyncSession) -> None:
    kot, _ = await setup_stations(db_session)
    citizen = await make_user(db_session)
    await make_officer(db_session, kot, DutyStatus.AVAILABLE, located=True, **KOTWALI)

    response = await client.post(
        "/incidents/report",
        json={**KOTWALI, "description": "Noise complaint every night"},
        headers=auth(citizen),
    )

    assert response.status_code == 201
    assert response.json()["type"] == "report"
    assert response.json()["status"] == "pending"
    assert response.json()["officer"] is None


async def test_report_needs_a_description(client: AsyncClient, db_session: AsyncSession) -> None:
    await setup_stations(db_session)
    citizen = await make_user(db_session)

    response = await client.post("/incidents/report", json=KOTWALI, headers=auth(citizen))

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "description"


async def test_db_blocks_officer_with_two_active_incidents(db_session: AsyncSession) -> None:
    kot, _ = await setup_stations(db_session)
    citizen = await make_user(db_session)
    officer = await make_officer(db_session, kot, DutyStatus.BUSY)
    for _ in range(2):
        db_session.add(
            Incident(
                citizen_id=citizen.id,
                officer_id=officer.id,
                station_id=kot.id,
                type=IncidentType.REPORT,
                status=IncidentStatus.ASSIGNED,
                **KOTWALI,
            )
        )

    with pytest.raises(IntegrityError, match="uq_incidents_active_per_officer"):
        await db_session.flush()
