from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import local_now, local_today
from app.models.enums import DutyStatus, UserRole
from tests.factories import auth, make_officer, make_station, make_user


@pytest.fixture
async def world(db_session: AsyncSession) -> dict:
    kot = await make_station(db_session, code="KOT")
    jal = await make_station(db_session, code="JAL", lat=24.95)
    return {
        "kot": kot,
        "jal": jal,
        "citizen": await make_user(db_session),
        "admin": await make_user(db_session, UserRole.STATION_ADMIN, station=kot),
        "other_admin": await make_user(db_session, UserRole.STATION_ADMIN, station=jal),
    }


def gd_body(station_id: int, **overrides) -> dict:
    return {
        "station_id": station_id,
        "category": "lost_document",
        "title": "Lost national ID card",
        "details": "Lost my NID card near Zindabazar around 6 pm in a brown wallet.",
        "incident_date": local_today().isoformat(),
        **overrides,
    }


async def file_gd(client: AsyncClient, user, station_id: int, **overrides):
    return await client.post("/gds", json=gd_body(station_id, **overrides), headers=auth(user))


async def review(client: AsyncClient, gd_number: str, user, action: str, note=None):
    body = {"action": action} | ({"note": note} if note else {})
    return await client.patch(f"/gds/{gd_number}/review", json=body, headers=auth(user))


async def test_gd_numbers_count_per_station(client: AsyncClient, world: dict) -> None:
    year = local_now().year

    first = await file_gd(client, world["citizen"], world["kot"].id)
    second = await file_gd(client, world["citizen"], world["kot"].id)
    other = await file_gd(client, world["citizen"], world["jal"].id)

    assert first.status_code == 201
    assert first.json()["gd_number"] == f"SYL-KOT-{year}-000001"
    assert second.json()["gd_number"] == f"SYL-KOT-{year}-000002"
    assert other.json()["gd_number"] == f"SYL-JAL-{year}-000001"
    assert first.json()["status"] == "submitted"


async def test_client_cannot_set_number_or_status(client: AsyncClient, world: dict) -> None:
    response = await file_gd(
        client, world["citizen"], world["kot"].id, gd_number="X-1", status="approved"
    )

    assert response.json()["status"] == "submitted"
    assert response.json()["gd_number"] != "X-1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("incident_date", (local_today() + timedelta(days=1)).isoformat()),
        ("category", "murder"),
        ("title", "abc"),
        ("details", "too short"),
        ("station_id", 999999),
    ],
)
async def test_invalid_gd_is_422(client: AsyncClient, world: dict, field: str, value) -> None:
    body = gd_body(world["kot"].id) | {field: value}
    response = await client.post("/gds", json=body, headers=auth(world["citizen"]))

    assert response.status_code == 422
    assert field in [d["field"] for d in response.json()["error"]["details"]]


async def test_officer_cannot_file_or_read_gds(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    officer = await make_officer(db_session, world["kot"], DutyStatus.AVAILABLE)

    assert (await file_gd(client, officer.user, world["kot"].id)).status_code == 403
    assert (await client.get("/gds", headers=auth(officer.user))).status_code == 403


async def test_review_flow(client: AsyncClient, world: dict) -> None:
    number = (await file_gd(client, world["citizen"], world["kot"].id)).json()["gd_number"]

    started = await review(client, number, world["admin"], "start_review")
    approved = await review(client, number, world["admin"], "approve")

    assert started.json()["status"] == "under_review"
    assert started.json()["reviewed_by"] is None
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] == world["admin"].id
    assert approved.json()["reviewed_at"] is not None


async def test_reject_requires_note(client: AsyncClient, world: dict) -> None:
    number = (await file_gd(client, world["citizen"], world["kot"].id)).json()["gd_number"]
    await review(client, number, world["admin"], "start_review")

    no_note = await review(client, number, world["admin"], "reject")
    with_note = await review(client, number, world["admin"], "reject", note="Wrong station")

    assert no_note.status_code == 422
    assert with_note.json()["status"] == "rejected"
    assert with_note.json()["review_note"] == "Wrong station"


async def test_cannot_skip_review_or_change_final(client: AsyncClient, world: dict) -> None:
    number = (await file_gd(client, world["citizen"], world["kot"].id)).json()["gd_number"]

    skip = await review(client, number, world["admin"], "approve")
    await review(client, number, world["admin"], "start_review")
    await review(client, number, world["admin"], "approve")
    again = await review(client, number, world["admin"], "reject", note="Changed my mind")

    assert skip.status_code == 409
    assert skip.json()["error"]["code"] == "INVALID_TRANSITION"
    assert again.status_code == 409


async def test_other_station_admin_cannot_review_or_see(client: AsyncClient, world: dict) -> None:
    number = (await file_gd(client, world["citizen"], world["kot"].id)).json()["gd_number"]

    reviewed = await review(client, number, world["other_admin"], "start_review")
    seen = await client.get(f"/gds/{number}", headers=auth(world["other_admin"]))

    assert reviewed.status_code == 404
    assert seen.status_code == 404


async def test_gd_visibility_and_list(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    mine = (await file_gd(client, world["citizen"], world["kot"].id)).json()["gd_number"]
    stranger = await make_user(db_session)
    await file_gd(client, stranger, world["jal"].id)
    super_admin = await make_user(db_session, UserRole.SUPER_ADMIN)

    assert (await client.get(f"/gds/{mine}", headers=auth(world["citizen"]))).status_code == 200
    assert (await client.get(f"/gds/{mine}", headers=auth(stranger))).status_code == 404
    own = (await client.get("/gds", headers=auth(world["citizen"]))).json()
    station = (await client.get("/gds", headers=auth(world["admin"]))).json()
    everything = (await client.get("/gds", headers=auth(super_admin))).json()
    filtered = (
        await client.get(f"/gds?station_id={world['jal'].id}", headers=auth(super_admin))
    ).json()

    assert [g["gd_number"] for g in own["items"]] == [mine]
    assert station["total"] == 1
    assert everything["total"] == 2
    assert filtered["total"] == 1
