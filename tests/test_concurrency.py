"""Races that the per-test rollback fixture can't show: every request here commits for real,
on its own connection, and the tables are truncated afterwards."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.security import create_refresh_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import DutyStatus, UserRole
from app.models.refresh_token import RefreshToken
from app.repositories.officer_repository import OfficerRepository
from tests.conftest import TEST_DATABASE_URL
from tests.factories import auth, make_officer, make_station, make_user

SPOT = {"lat": 24.8949, "lng": 91.8687}


@pytest.fixture
async def real() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def own_session_per_request() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = own_session_per_request
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/api/v1"
        ) as client:
            yield client, maker
    finally:
        app.dependency_overrides.clear()
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await engine.dispose()


async def test_two_sos_at_once_never_share_an_officer(real) -> None:
    client, maker = real
    async with maker() as db:
        station = await make_station(db, **SPOT)
        only_officer = await make_officer(db, station, DutyStatus.AVAILABLE, located=True, **SPOT)
        citizens = [await make_user(db) for _ in range(2)]
        await db.commit()

    responses = await asyncio.gather(
        *(client.post("/incidents/sos", json=SPOT, headers=auth(c)) for c in citizens)
    )

    assert [r.status_code for r in responses] == [201, 201]
    statuses = sorted(r.json()["status"] for r in responses)
    assert statuses == ["assigned", "pending"]
    assigned = next(r.json() for r in responses if r.json()["status"] == "assigned")
    assert assigned["officer"]["id"] == only_officer.id


async def test_skip_locked_moves_on_to_the_next_officer(real) -> None:
    """Deterministic proof: while one transaction holds the nearest officer, a second one
    gets the next-nearest instead of waiting or taking the same officer."""
    _, maker = real
    async with maker() as db:
        station = await make_station(db, **SPOT)
        nearest = await make_officer(db, station, DutyStatus.AVAILABLE, located=True, **SPOT)
        second = await make_officer(
            db, station, DutyStatus.AVAILABLE, located=True, lat=24.9, lng=91.88
        )
        await db.commit()

    async with maker() as first, maker() as other:
        held = await OfficerRepository(first).nearest_reachable_for_update(**SPOT)
        got = await OfficerRepository(other).nearest_reachable_for_update(**SPOT)
        assert held.id == nearest.id
        assert got.id == second.id
        await first.rollback()
        await other.rollback()


async def test_same_citizen_double_tap_creates_one_sos(real) -> None:
    client, maker = real
    async with maker() as db:
        await make_station(db, **SPOT)
        citizen = await make_user(db)
        await db.commit()

    responses = await asyncio.gather(
        *(client.post("/incidents/sos", json=SPOT, headers=auth(citizen)) for _ in range(2))
    )

    assert sorted(r.status_code for r in responses) == [201, 409]


async def test_refresh_token_can_be_used_only_once_under_race(real) -> None:
    client, maker = real
    async with maker() as db:
        user = await make_user(db)
        issued = create_refresh_token(user.id)
        db.add(RefreshToken(user_id=user.id, jti=issued.jti, expires_at=issued.expires_at))
        await db.commit()

    responses = await asyncio.gather(
        *(client.post("/auth/refresh", json={"refresh_token": issued.token}) for _ in range(3))
    )

    assert sorted(r.status_code for r in responses) == [200, 401, 401]


async def test_parallel_gds_get_distinct_consecutive_numbers(real) -> None:
    client, maker = real
    async with maker() as db:
        station = await make_station(db, code="KOT")
        citizens = [await make_user(db) for _ in range(5)]
        await db.commit()
    body = {
        "station_id": station.id,
        "category": "lost_item",
        "title": "Lost phone",
        "details": "Lost a black phone on the bus to Ambarkhana this morning.",
        "incident_date": "2026-10-01",
    }

    responses = await asyncio.gather(
        *(client.post("/gds", json=body, headers=auth(c)) for c in citizens)
    )

    numbers = sorted(r.json()["gd_number"][-6:] for r in responses)
    assert numbers == ["000001", "000002", "000003", "000004", "000005"]


async def test_station_admin_role_check_in_real_transaction(real) -> None:
    """Smoke test that committed data and role guards work with a real session per request."""
    client, maker = real
    async with maker() as db:
        station = await make_station(db)
        admin = await make_user(db, UserRole.STATION_ADMIN, station=station)
        await db.commit()

    response = await client.get("/officers", headers=auth(admin))

    assert response.status_code == 200
