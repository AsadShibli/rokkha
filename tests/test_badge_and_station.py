from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DutyStatus
from tests.factories import auth, make_officer, make_station, make_user

SPOT = {"lat": 24.8949, "lng": 91.8687}


async def test_citizen_sees_officer_badge_and_thana(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    kot = await make_station(db_session, code="KOT", name="Kotwali", **SPOT)
    jal = await make_station(db_session, code="JAL", name="Jalalabad", lat=24.93, lng=91.87)
    # The nearest free officer belongs to another thana than the incident's jurisdiction.
    officer = await make_officer(db_session, jal, DutyStatus.AVAILABLE, located=True, **SPOT)
    citizen = await make_user(db_session)

    created = (await client.post("/incidents/sos", json=SPOT, headers=auth(citizen))).json()
    seen = (await client.get(f"/incidents/{created['id']}", headers=auth(citizen))).json()

    for body in (created, seen):
        assert body["station"] == {"id": kot.id, "name": "Kotwali", "code": "KOT"}
        assert body["officer"]["badge_no"] == officer.badge_no
        assert body["officer"]["station"] == {"id": jal.id, "name": "Jalalabad", "code": "JAL"}


async def test_gd_shows_its_thana(client: AsyncClient, db_session: AsyncSession) -> None:
    kot = await make_station(db_session, code="KOT", name="Kotwali")
    citizen = await make_user(db_session)
    body = {
        "station_id": kot.id,
        "category": "lost_item",
        "title": "Lost phone",
        "details": "Lost a black phone on the bus to Ambarkhana this morning.",
        "incident_date": "2026-10-01",
    }

    filed = (await client.post("/gds", json=body, headers=auth(citizen))).json()
    listed = (await client.get("/gds", headers=auth(citizen))).json()["items"][0]

    assert filed["station"] == {"id": kot.id, "name": "Kotwali", "code": "KOT"}
    assert listed["station"]["name"] == "Kotwali"
