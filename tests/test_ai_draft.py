import json
from datetime import timedelta
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_client
from app.core.config import Settings
from app.core.time import local_today
from app.main import app
from app.models.enums import DutyStatus
from tests.factories import auth, make_officer, make_station, make_user

COMPLAINT = {"text": "Lost my wallet with my NID card near Zindabazar yesterday evening."}
GOOD_DRAFT = {
    "category": "lost_document",
    "title": "Lost wallet with NID card",
    "details": "My wallet containing my national ID card was lost near Zindabazar.",
    "incident_date": (local_today() - timedelta(days=1)).isoformat(),
}


class FakeClaude:
    """Stands in for AsyncAnthropic: records the request, returns a canned response."""

    def __init__(self, *, text: str | None = None, stop_reason="end_turn", error=None):
        self.requests: list[dict] = []
        self._text, self._stop, self._error = text, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        if self._error:
            raise self._error
        content = [] if self._text is None else [SimpleNamespace(type="text", text=self._text)]
        return SimpleNamespace(stop_reason=self._stop, stop_details=None, content=content)


def use(fake) -> None:
    app.dependency_overrides[get_ai_client] = lambda: fake


async def draft(client: AsyncClient, user, body=COMPLAINT):
    return await client.post("/gds/ai-draft", json=body, headers=auth(user))


async def test_returns_validated_draft(client: AsyncClient, db_session: AsyncSession) -> None:
    fake = FakeClaude(text=json.dumps(GOOD_DRAFT))
    use(fake)
    citizen = await make_user(db_session)

    response = await draft(client, citizen)

    assert response.status_code == 200
    assert response.json() == GOOD_DRAFT
    sent = fake.requests[0]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["output_config"]["effort"] == "low"
    assert sent["fallbacks"] == "default"
    assert "Zindabazar" in sent["messages"][0]["content"]
    assert f"Today is {local_today().isoformat()}" in sent["messages"][0]["content"]


async def test_future_date_is_dropped(client: AsyncClient, db_session: AsyncSession) -> None:
    future = {**GOOD_DRAFT, "incident_date": (local_today() + timedelta(days=3)).isoformat()}
    use(FakeClaude(text=json.dumps(future)))

    response = await draft(client, await make_user(db_session))

    assert response.json()["incident_date"] is None


def timeout_error() -> Exception:
    return anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com"))


@pytest.mark.parametrize(
    "fake",
    [
        FakeClaude(text="not json"),
        FakeClaude(text=json.dumps({**GOOD_DRAFT, "category": "murder"})),
        FakeClaude(text=json.dumps({**GOOD_DRAFT, "title": "x"})),
        FakeClaude(text=None),
        FakeClaude(text="{}", stop_reason="refusal"),
        FakeClaude(error=timeout_error()),
        None,  # no API key configured
    ],
    ids=["not_json", "bad_category", "short_title", "no_text", "refusal", "timeout", "no_key"],
)
async def test_any_ai_failure_is_503(client: AsyncClient, db_session: AsyncSession, fake) -> None:
    use(fake)

    response = await draft(client, await make_user(db_session))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_UNAVAILABLE"


async def test_only_citizens_and_text_is_validated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    use(FakeClaude(text=json.dumps(GOOD_DRAFT)))
    officer = await make_officer(db_session, await make_station(db_session), DutyStatus.AVAILABLE)

    assert (await draft(client, officer.user)).status_code == 403
    assert (await draft(client, await make_user(db_session), {"text": "hi"})).status_code == 422


def test_hosted_postgres_urls_get_asyncpg_driver() -> None:
    settings = Settings(database_url="postgres://u:p@host:5432/db")

    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"
