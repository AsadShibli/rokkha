import pytest
import redis
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def worker_enabled(monkeypatch: pytest.MonkeyPatch):
    try:
        redis.Redis.from_url(get_settings().redis_url).ping()
    except redis.RedisError:
        pytest.skip("Redis not reachable")
    monkeypatch.setenv("RUN_WORKER_IN_PROCESS", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_api_starts_and_stops_the_worker(worker_enabled) -> None:
    with TestClient(app):
        task = app.state.worker_task
        assert task is not None and not task.done()

    assert task.done()


def test_worker_is_off_by_default() -> None:
    with TestClient(app):
        assert app.state.worker_task is None
