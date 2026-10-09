import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_job_queue, get_rate_limiter
from app.core.config import get_settings
from app.main import app
from app.models.enums import DutyStatus, IncidentStatus
from app.repositories.incident_repository import IncidentRepository
from app.services.dispatch_service import DispatchService
from app.services.rate_limit import RateDecision, RedisRateLimiter
from tests.factories import auth, make_officer, make_station, make_user

SPOT = {"lat": 24.8949, "lng": 91.8687}


class RecordingQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[int, int]] = []

    async def schedule_escalation(self, incident_id: int, officer_id: int) -> None:
        self.jobs.append((incident_id, officer_id))


class MemoryRateLimiter:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        self.counts[key] = self.counts.get(key, 0) + 1
        allowed = self.counts[key] <= limit
        return RateDecision(allowed=allowed, retry_after=0 if allowed else window_seconds)


@pytest.fixture
def queue(client: AsyncClient) -> RecordingQueue:
    recorder = RecordingQueue()
    app.dependency_overrides[get_job_queue] = lambda: recorder
    return recorder


async def sos(client: AsyncClient, citizen) -> dict:
    response = await client.post("/incidents/sos", json=SPOT, headers=auth(citizen))
    assert response.status_code == 201, response.text
    return response.json()


# --- scheduling ----------------------------------------------------------------------------


async def test_assigned_sos_schedules_an_escalation_check(
    client: AsyncClient, db_session: AsyncSession, queue: RecordingQueue
) -> None:
    station = await make_station(db_session, **SPOT)
    officer = await make_officer(db_session, station, DutyStatus.AVAILABLE, located=True, **SPOT)

    incident = await sos(client, await make_user(db_session))

    assert queue.jobs == [(incident["id"], officer.id)]


async def test_pending_sos_schedules_nothing(
    client: AsyncClient, db_session: AsyncSession, queue: RecordingQueue
) -> None:
    await make_station(db_session, **SPOT)

    await sos(client, await make_user(db_session))

    assert queue.jobs == []


# --- escalation logic ----------------------------------------------------------------------


@pytest.fixture
async def assigned(client: AsyncClient, db_session: AsyncSession) -> dict:
    station = await make_station(db_session, **SPOT)
    first = await make_officer(db_session, station, DutyStatus.AVAILABLE, located=True, **SPOT)
    citizen = await make_user(db_session)
    incident = await sos(client, citizen)
    return {"incident": incident, "first": first, "station": station, "citizen": citizen}


async def test_unaccepted_sos_moves_to_next_officer(
    db_session: AsyncSession, assigned: dict
) -> None:
    second = await make_officer(
        db_session, assigned["station"], DutyStatus.AVAILABLE, located=True, lat=24.9, lng=91.88
    )

    incident = await DispatchService(db_session).escalate(
        assigned["incident"]["id"], assigned["first"].id
    )

    assert incident.status == IncidentStatus.ASSIGNED
    assert incident.officer_id == second.id
    last = incident.events[-1]
    assert (last.from_status, last.to_status, last.actor_id) == ("assigned", "assigned", None)
    assert "Escalated" in last.note
    await db_session.refresh(assigned["first"])
    assert assigned["first"].duty_status == DutyStatus.AVAILABLE


async def test_escalation_never_returns_to_an_officer_who_had_it(
    db_session: AsyncSession, assigned: dict
) -> None:
    second = await make_officer(
        db_session, assigned["station"], DutyStatus.AVAILABLE, located=True, lat=24.9, lng=91.88
    )
    dispatch = DispatchService(db_session)
    await dispatch.escalate(assigned["incident"]["id"], assigned["first"].id)

    incident = await dispatch.escalate(assigned["incident"]["id"], second.id)

    # The first officer is free and nearest again, but already let it time out.
    assert incident.status == IncidentStatus.PENDING
    assert incident.officer_id is None


async def test_escalation_without_other_officer_goes_pending(
    db_session: AsyncSession, assigned: dict
) -> None:
    incident = await DispatchService(db_session).escalate(
        assigned["incident"]["id"], assigned["first"].id
    )

    assert incident.status == IncidentStatus.PENDING
    assert incident.officer_id is None
    assert incident.events[-1].to_status == IncidentStatus.PENDING


async def test_escalation_is_noop_once_accepted(
    client: AsyncClient, db_session: AsyncSession, assigned: dict
) -> None:
    await client.post(
        f"/incidents/{assigned['incident']['id']}/accept", headers=auth(assigned["first"].user)
    )

    result = await DispatchService(db_session).escalate(
        assigned["incident"]["id"], assigned["first"].id
    )

    assert result is None
    incident = await IncidentRepository(db_session).get_with_events(assigned["incident"]["id"])
    assert incident.status == IncidentStatus.EN_ROUTE


async def test_escalation_is_noop_for_stale_officer(
    db_session: AsyncSession, assigned: dict
) -> None:
    result = await DispatchService(db_session).escalate(assigned["incident"]["id"], 999999)

    assert result is None


# --- rate limit ----------------------------------------------------------------------------


async def test_fourth_sos_in_window_is_429(client: AsyncClient, db_session: AsyncSession) -> None:
    app.dependency_overrides[get_rate_limiter] = MemoryRateLimiter
    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    await make_station(db_session, **SPOT)
    citizen = await make_user(db_session)

    for _ in range(3):
        incident = await sos(client, citizen)
        await client.post(f"/incidents/{incident['id']}/cancel", headers=auth(citizen))
    blocked = await client.post("/incidents/sos", json=SPOT, headers=auth(citizen))

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert blocked.headers["retry-after"] == "600"


async def test_redis_rate_limiter_counts_per_window() -> None:
    redis = aioredis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception:
        pytest.skip("Redis not reachable")
    key = "rate:test:window"
    await redis.delete(key)
    limiter = RedisRateLimiter(redis)

    decisions = [await limiter.hit(key, limit=2, window_seconds=60) for _ in range(3)]

    assert [d.allowed for d in decisions] == [True, True, False]
    assert 0 < decisions[-1].retry_after <= 60
    await redis.delete(key)
    await redis.aclose()
