import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.factories import PASSWORD, auth, make_station, make_user

NEW_STATION = {
    "name": "Jalalabad",
    "code": "JAL",
    "city": "Sylhet",
    "city_code": "SYL",
    "lat": 24.92,
    "lng": 91.85,
}


async def test_super_admin_creates_station(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)

    response = await client.post("/stations", json=NEW_STATION, headers=auth(admin))

    assert response.status_code == 201
    assert response.json()["code"] == "JAL"


@pytest.mark.parametrize("role", [UserRole.CITIZEN, UserRole.OFFICER, UserRole.STATION_ADMIN])
async def test_only_super_admin_creates_stations(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    station = await make_station(db_session) if role == UserRole.STATION_ADMIN else None
    user = await make_user(db_session, role, station=station)

    response = await client.post("/stations", json=NEW_STATION, headers=auth(user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_duplicate_code_and_name_are_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)
    await make_station(db_session, code="JAL", name="Jalalabad")

    response = await client.post("/stations", json=NEW_STATION, headers=auth(admin))

    assert response.status_code == 409
    assert {d["field"] for d in response.json()["error"]["details"]} == {"code", "name"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("lat", 40.7), ("lng", 74.0), ("code", "jal"), ("code", "TOOLONG"), ("city_code", "SY")],
)
async def test_invalid_station_is_422(
    client: AsyncClient, db_session: AsyncSession, field: str, value
) -> None:
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)

    response = await client.post(
        "/stations", json={**NEW_STATION, field: value}, headers=auth(admin)
    )

    assert response.status_code == 422
    assert field in [d["field"] for d in response.json()["error"]["details"]]


async def test_any_user_lists_stations_paginated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    citizen = await make_user(db_session)
    for code in ("AAA", "BBB", "CCC"):
        await make_station(db_session, code=code)
    await make_station(db_session, code="DHK", city="Dhaka", city_code="DHA")

    page = await client.get("/stations?page=1&page_size=2&city=sylhet", headers=auth(citizen))

    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["page_size"] == 2
    assert [s["code"] for s in body["items"]] == ["AAA", "BBB"]


async def test_page_size_over_100_is_422(client: AsyncClient, db_session: AsyncSession) -> None:
    citizen = await make_user(db_session)

    response = await client.get("/stations?page_size=101", headers=auth(citizen))

    assert response.status_code == 422


async def test_super_admin_creates_station_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)
    station = await make_station(db_session)

    response = await client.post(
        f"/stations/{station.id}/admins",
        json={
            "name": "OC Kotwali",
            "phone": "+8801811111111",
            "password": PASSWORD,
            "role": "super_admin",
        },
        headers=auth(admin),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "station_admin"
    assert response.json()["station_id"] == station.id


async def test_station_admin_for_missing_station_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await make_user(db_session, UserRole.SUPER_ADMIN)

    response = await client.post(
        "/stations/999999/admins",
        json={"name": "Nobody", "phone": "+8801811111111", "password": PASSWORD},
        headers=auth(admin),
    )

    assert response.status_code == 404


async def test_db_rejects_station_admin_without_station(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_users_station_admin_station"):
        await make_user(db_session, UserRole.STATION_ADMIN)
