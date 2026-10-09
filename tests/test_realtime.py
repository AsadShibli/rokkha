"""Live updates. Publishing is checked with a recording publisher; the WebSocket end-to-end
tests run the full app (lifespan, real Redis, committed data) through Starlette's TestClient."""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
import redis
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_publisher
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import DutyStatus
from tests.conftest import TEST_DATABASE_URL
from tests.factories import auth, make_officer, make_station, make_user

SPOT = {"lat": 24.8949, "lng": 91.8687}


class RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[int, dict[str, Any]]] = []

    async def publish(self, incident_id: int, message: dict[str, Any]) -> None:
        self.messages.append((incident_id, message))


@pytest.fixture
def published(client: AsyncClient) -> RecordingPublisher:
    recorder = RecordingPublisher()
    app.dependency_overrides[get_publisher] = lambda: recorder
    return recorder


async def test_lifecycle_and_location_are_published(
    client: AsyncClient, db_session: AsyncSession, published: RecordingPublisher
) -> None:
    station = await make_station(db_session, **SPOT)
    officer = await make_officer(db_session, station, DutyStatus.AVAILABLE, located=True, **SPOT)
    citizen = await make_user(db_session)
    incident = (await client.post("/incidents/sos", json=SPOT, headers=auth(citizen))).json()

    await client.post(f"/incidents/{incident['id']}/accept", headers=auth(officer.user))
    await client.patch(
        "/officers/me/location", json={"lat": 24.9, "lng": 91.87}, headers=auth(officer.user)
    )
    await client.post(f"/incidents/{incident['id']}/resolve", headers=auth(officer.user))
    # No active incident any more: location updates are not published.
    await client.patch(
        "/officers/me/location", json={"lat": 24.91, "lng": 91.87}, headers=auth(officer.user)
    )

    kinds = [(i, m["type"], m.get("incident", {}).get("status")) for i, m in published.messages]
    assert kinds == [
        (incident["id"], "status", "en_route"),
        (incident["id"], "location", None),
        (incident["id"], "status", "resolved"),
    ]
    assert published.messages[1][1]["lat"] == 24.9


# --- WebSocket end to end ----------------------------------------------------------------


def redis_available() -> bool:
    try:
        return redis.Redis.from_url(get_settings().redis_url).ping()
    except redis.RedisError:
        return False


@pytest.fixture
def live() -> Iterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    if not redis_available():
        pytest.skip("Redis not reachable (docker compose up -d redis)")
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def own_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    with TestClient(app) as client:  # runs the lifespan -> real Redis client
        yield client, maker
    app.dependency_overrides.clear()

    async def truncate() -> None:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await engine.dispose()

    asyncio.run(truncate())


def setup_assigned_sos(client: TestClient, maker) -> tuple[int, Any, Any]:
    async def create():
        async with maker() as db:
            station = await make_station(db, **SPOT)
            officer = await make_officer(db, station, DutyStatus.AVAILABLE, located=True, **SPOT)
            citizen = await make_user(db)
            stranger = await make_user(db)
            await db.commit()
            return officer, citizen, stranger

    officer, citizen, stranger = asyncio.run(create())
    response = client.post("/api/v1/incidents/sos", json=SPOT, headers=auth(citizen))
    return response.json()["id"], (officer, citizen), stranger


def ws_url(incident_id: int, user) -> str:
    return f"/api/v1/ws/incidents/{incident_id}?token={create_access_token(user.id).token}"


def test_owner_gets_snapshot_then_live_updates(live) -> None:
    client, maker = live
    incident_id, (officer, citizen), _ = setup_assigned_sos(client, maker)

    with client.websocket_connect(ws_url(incident_id, citizen)) as ws:
        snapshot = ws.receive_json()
        client.post(f"/api/v1/incidents/{incident_id}/accept", headers=auth(officer.user))
        status_update = ws.receive_json()
        client.patch(
            "/api/v1/officers/me/location",
            json={"lat": 24.9, "lng": 91.87},
            headers=auth(officer.user),
        )
        location_update = ws.receive_json()
        ws.send_text("ping")
        pong = ws.receive_text()

    assert snapshot["type"] == "snapshot"
    assert snapshot["incident"]["status"] == "assigned"
    assert status_update["type"] == "status"
    assert status_update["incident"]["status"] == "en_route"
    assert location_update == {**location_update, "type": "location", "lat": 24.9, "lng": 91.87}
    assert pong == "pong"


def test_bad_token_is_closed_4401(live) -> None:
    client, maker = live
    incident_id, _, _ = setup_assigned_sos(client, maker)

    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(f"/api/v1/ws/incidents/{incident_id}?token=nope"),
    ):
        pass

    assert closed.value.code == 4401


def test_stranger_is_closed_4404(live) -> None:
    client, maker = live
    incident_id, _, stranger = setup_assigned_sos(client, maker)

    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(ws_url(incident_id, stranger)),
    ):
        pass

    assert closed.value.code == 4404


def test_client_may_only_ping(live) -> None:
    client, maker = live
    incident_id, (_, citizen), _ = setup_assigned_sos(client, maker)

    with client.websocket_connect(ws_url(incident_id, citizen)) as ws:
        ws.receive_json()  # snapshot
        ws.send_text("hello")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()

    assert closed.value.code == 1008
