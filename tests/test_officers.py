import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus, UserRole
from tests.factories import PASSWORD, auth, make_officer, make_station, make_user

NEW_OFFICER = {
    "name": "Karim Ahmed",
    "phone": "+8801912345678",
    "password": PASSWORD,
    "badge_no": "KOT-1043",
    "rank": "Sub-Inspector",
}


async def test_station_admin_creates_officer_in_own_station(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    own = await make_station(db_session, code="KOT")
    other = await make_station(db_session, code="JAL")
    admin = await make_user(db_session, UserRole.STATION_ADMIN, station=own)

    response = await client.post(
        "/officers",
        json={**NEW_OFFICER, "station_id": other.id, "duty_status": "available"},
        headers=auth(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["station_id"] == own.id  # client-sent station_id ignored
    assert body["duty_status"] == "off_duty"  # always starts off duty
    assert body["user"]["name"] == "Karim Ahmed"

    login = await client.post(
        "/auth/login", json={"phone": NEW_OFFICER["phone"], "password": PASSWORD}
    )
    me = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert me.json()["role"] == "officer"
    assert me.json()["officer"]["badge_no"] == "KOT-1043"


async def test_duplicate_badge_and_phone_are_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    station = await make_station(db_session)
    admin = await make_user(db_session, UserRole.STATION_ADMIN, station=station)
    await client.post("/officers", json=NEW_OFFICER, headers=auth(admin))

    response = await client.post("/officers", json=NEW_OFFICER, headers=auth(admin))

    assert response.status_code == 409
    assert {d["field"] for d in response.json()["error"]["details"]} == {"phone", "badge_no"}


@pytest.mark.parametrize("role", [UserRole.CITIZEN, UserRole.SUPER_ADMIN])
async def test_only_station_admin_creates_officers(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    user = await make_user(db_session, role)

    response = await client.post("/officers", json=NEW_OFFICER, headers=auth(user))

    assert response.status_code == 403


async def test_station_admin_lists_only_own_station(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    own = await make_station(db_session, code="KOT")
    other = await make_station(db_session, code="JAL")
    admin = await make_user(db_session, UserRole.STATION_ADMIN, station=own)
    mine = await make_officer(db_session, own)
    await make_officer(db_session, other)

    # Asking for the other station is ignored for station admins.
    response = await client.get(f"/officers?station_id={other.id}", headers=auth(admin))

    assert response.status_code == 200
    assert [o["id"] for o in response.json()["items"]] == [mine.id]


async def test_super_admin_filters_by_station_and_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot = await make_station(db_session, code="KOT")
    jal = await make_station(db_session, code="JAL")
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)
    available = await make_officer(db_session, kot, DutyStatus.AVAILABLE)
    await make_officer(db_session, kot, DutyStatus.OFF_DUTY)
    await make_officer(db_session, jal, DutyStatus.AVAILABLE)

    response = await client.get(
        f"/officers?station_id={kot.id}&duty_status=available", headers=auth(admin)
    )

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == available.id


async def test_citizen_cannot_list_officers(client: AsyncClient, db_session: AsyncSession) -> None:
    citizen = await make_user(db_session)

    response = await client.get("/officers", headers=auth(citizen))

    assert response.status_code == 403


# --- duty status -------------------------------------------------------------------------


async def test_officer_goes_on_and_off_duty(client: AsyncClient, db_session: AsyncSession) -> None:
    officer = await make_officer(db_session, await make_station(db_session))

    on = await client.patch(
        "/officers/me/status", json={"duty_status": "available"}, headers=auth(officer.user)
    )
    off = await client.patch(
        "/officers/me/status", json={"duty_status": "off_duty"}, headers=auth(officer.user)
    )

    assert on.status_code == 200 and on.json()["duty_status"] == "available"
    assert off.status_code == 200 and off.json()["duty_status"] == "off_duty"


async def test_officer_cannot_set_busy(client: AsyncClient, db_session: AsyncSession) -> None:
    officer = await make_officer(db_session, await make_station(db_session))

    response = await client.patch(
        "/officers/me/status", json={"duty_status": "busy"}, headers=auth(officer.user)
    )

    assert response.status_code == 422


async def test_busy_officer_cannot_change_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    officer = await make_officer(db_session, await make_station(db_session), DutyStatus.BUSY)

    response = await client.patch(
        "/officers/me/status", json={"duty_status": "off_duty"}, headers=auth(officer.user)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OFFICER_BUSY"


async def test_citizen_cannot_set_duty_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    citizen = await make_user(db_session)

    response = await client.patch(
        "/officers/me/status", json={"duty_status": "available"}, headers=auth(citizen)
    )

    assert response.status_code == 403


# --- location ----------------------------------------------------------------------------


async def test_location_update_sets_last_seen(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    officer = await make_officer(db_session, await make_station(db_session))

    response = await client.patch(
        "/officers/me/location", json={"lat": 24.9, "lng": 91.87}, headers=auth(officer.user)
    )

    assert response.status_code == 204
    me = (await client.get("/users/me", headers=auth(officer.user))).json()["officer"]
    assert (me["last_lat"], me["last_lng"]) == (24.9, 91.87)
    assert me["last_seen_at"] is not None
    assert me["duty_status"] == "off_duty"  # location never changes duty status


async def test_location_outside_bangladesh_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    officer = await make_officer(db_session, await make_station(db_session))

    response = await client.patch(
        "/officers/me/location", json={"lat": 51.5, "lng": -0.12}, headers=auth(officer.user)
    )

    assert response.status_code == 422
    assert {d["field"] for d in response.json()["error"]["details"]} == {"lat", "lng"}
