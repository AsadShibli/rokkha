from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus, UserRole
from tests.factories import auth, make_officer, make_station, make_user

SPOT = {"lat": 24.8949, "lng": 91.8687}


@pytest.fixture
async def world(db_session: AsyncSession) -> dict:
    """One station with an admin, one reachable officer, a spare officer, and a citizen."""
    kot = await make_station(db_session, code="KOT", **SPOT)
    jal = await make_station(db_session, code="JAL", lat=24.95, lng=91.87)
    return {
        "kot": kot,
        "jal": jal,
        "admin": await make_user(db_session, UserRole.STATION_ADMIN, station=kot),
        "other_admin": await make_user(db_session, UserRole.STATION_ADMIN, station=jal),
        "officer": await make_officer(db_session, kot, DutyStatus.AVAILABLE, located=True, **SPOT),
        "spare": await make_officer(
            db_session, kot, DutyStatus.AVAILABLE, located=True, lat=24.9, lng=91.88
        ),
        "citizen": await make_user(db_session),
    }


async def raise_sos(client: AsyncClient, citizen) -> dict:
    response = await client.post("/incidents/sos", json=SPOT, headers=auth(citizen))
    assert response.status_code == 201
    return response.json()


async def act(client: AsyncClient, incident_id: int, action: str, user, **body):
    return await client.post(
        f"/incidents/{incident_id}/{action}", json=body or None, headers=auth(user)
    )


async def test_full_happy_path(client: AsyncClient, world: dict, db_session) -> None:
    incident = await raise_sos(client, world["citizen"])
    assert incident["officer"]["id"] == world["officer"].id

    accepted = await act(client, incident["id"], "accept", world["officer"].user, note="On my way")
    resolved = await act(client, incident["id"], "resolve", world["officer"].user)

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "en_route"
    assert accepted.json()["accepted_at"] is not None
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert [e["to_status"] for e in resolved.json()["events"]] == [
        "pending",
        "assigned",
        "en_route",
        "resolved",
    ]
    await db_session.refresh(world["officer"])
    assert world["officer"].duty_status == DutyStatus.AVAILABLE


async def test_other_officer_cannot_accept(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])

    response = await act(client, incident["id"], "accept", world["spare"].user)

    assert response.status_code == 404


async def test_resolve_before_accept_is_409(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])

    response = await act(client, incident["id"], "resolve", world["officer"].user)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_accept_twice_is_409(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])
    await act(client, incident["id"], "accept", world["officer"].user)

    response = await act(client, incident["id"], "accept", world["officer"].user)

    assert response.status_code == 409


async def test_cancel_assigned_frees_officer(client: AsyncClient, world: dict, db_session) -> None:
    incident = await raise_sos(client, world["citizen"])

    response = await act(client, incident["id"], "cancel", world["citizen"], note="False alarm")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancelled_at"] is not None
    await db_session.refresh(world["officer"])
    assert world["officer"].duty_status == DutyStatus.AVAILABLE


async def test_cannot_cancel_once_en_route(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])
    await act(client, incident["id"], "accept", world["officer"].user)

    response = await act(client, incident["id"], "cancel", world["citizen"])

    assert response.status_code == 409


async def test_other_citizen_cannot_cancel(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    incident = await raise_sos(client, world["citizen"])
    stranger = await make_user(db_session)

    response = await act(client, incident["id"], "cancel", stranger)

    assert response.status_code == 404


# --- reassign ----------------------------------------------------------------------------


async def test_admin_reassigns_and_old_officer_is_freed(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    incident = await raise_sos(client, world["citizen"])
    await act(client, incident["id"], "accept", world["officer"].user)

    response = await act(
        client,
        incident["id"],
        "reassign",
        world["admin"],
        officer_id=world["spare"].id,
        note="Closer unit",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "assigned"
    assert body["officer"]["id"] == world["spare"].id
    assert body["accepted_at"] is None  # the new officer must accept again
    last = body["events"][-1]
    assert (last["from_status"], last["to_status"]) == ("en_route", "assigned")
    assert last["actor_id"] == world["admin"].id
    assert last["officer_id"] == world["spare"].id
    await db_session.refresh(world["officer"])
    await db_session.refresh(world["spare"])
    assert world["officer"].duty_status == DutyStatus.AVAILABLE
    assert world["spare"].duty_status == DutyStatus.BUSY


async def test_admin_assigns_pending_report(client: AsyncClient, world: dict) -> None:
    report = await client.post(
        "/incidents/report",
        json={**SPOT, "description": "Suspicious parcel by the gate"},
        headers=auth(world["citizen"]),
    )

    response = await act(
        client, report.json()["id"], "reassign", world["admin"], officer_id=world["spare"].id
    )

    assert response.status_code == 200
    assert response.json()["officer"]["id"] == world["spare"].id


async def test_reassign_to_unreachable_officer_is_409(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    incident = await raise_sos(client, world["citizen"])
    off_duty = await make_officer(db_session, world["kot"], DutyStatus.OFF_DUTY, located=True)
    other_station = await make_officer(db_session, world["jal"], DutyStatus.AVAILABLE, located=True)

    for target in (off_duty.id, other_station.id, world["officer"].id, 999999):
        response = await act(client, incident["id"], "reassign", world["admin"], officer_id=target)
        assert response.status_code == 409, target
        assert response.json()["error"]["code"] == "OFFICER_UNAVAILABLE"


async def test_reassign_by_other_station_admin_is_404(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])

    response = await act(
        client, incident["id"], "reassign", world["other_admin"], officer_id=world["spare"].id
    )

    assert response.status_code == 404


async def test_reassign_resolved_incident_is_409(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])
    await act(client, incident["id"], "accept", world["officer"].user)
    await act(client, incident["id"], "resolve", world["officer"].user)

    response = await act(
        client, incident["id"], "reassign", world["admin"], officer_id=world["spare"].id
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_citizen_cannot_reassign(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])

    response = await act(
        client, incident["id"], "reassign", world["citizen"], officer_id=world["spare"].id
    )

    assert response.status_code == 403


# --- reading -----------------------------------------------------------------------------


async def test_visibility_by_role(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    incident = await raise_sos(client, world["citizen"])
    stranger = await make_user(db_session)
    super_admin = await make_user(db_session, UserRole.SUPER_ADMIN)
    url = f"/incidents/{incident['id']}"

    async def status_for(user) -> int:
        return (await client.get(url, headers=auth(user))).status_code

    assert await status_for(world["citizen"]) == 200
    assert await status_for(world["officer"].user) == 200
    assert await status_for(world["admin"]) == 200
    assert await status_for(super_admin) == 200
    assert await status_for(stranger) == 404
    assert await status_for(world["spare"].user) == 404
    assert await status_for(world["other_admin"]) == 404


async def test_previous_officer_still_sees_incident(client: AsyncClient, world: dict) -> None:
    incident = await raise_sos(client, world["citizen"])
    await act(client, incident["id"], "reassign", world["admin"], officer_id=world["spare"].id)

    listed = await client.get("/incidents", headers=auth(world["officer"].user))

    assert [i["id"] for i in listed.json()["items"]] == [incident["id"]]


async def test_list_is_scoped_then_filtered(
    client: AsyncClient, world: dict, db_session: AsyncSession
) -> None:
    mine = await raise_sos(client, world["citizen"])
    other_citizen = await make_user(db_session)
    await client.post(
        "/incidents/report",
        json={**SPOT, "description": "Someone else's report"},
        headers=auth(other_citizen),
    )

    own = (await client.get("/incidents", headers=auth(world["citizen"]))).json()
    station = (await client.get("/incidents", headers=auth(world["admin"]))).json()
    sos_only = (
        await client.get("/incidents?type=sos&status=assigned", headers=auth(world["admin"]))
    ).json()
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    future = (await client.get(f"/incidents?from={tomorrow}", headers=auth(world["admin"]))).json()

    assert [i["id"] for i in own["items"]] == [mine["id"]]
    assert station["total"] == 2
    assert [i["id"] for i in sos_only["items"]] == [mine["id"]]
    assert future["total"] == 0


async def test_other_station_admin_sees_nothing(client: AsyncClient, world: dict) -> None:
    await raise_sos(client, world["citizen"])

    listed = await client.get("/incidents", headers=auth(world["other_admin"]))

    assert listed.json()["total"] == 0


async def test_bad_status_filter_is_422(client: AsyncClient, world: dict) -> None:
    response = await client.get("/incidents?status=lost", headers=auth(world["admin"]))

    assert response.status_code == 422
