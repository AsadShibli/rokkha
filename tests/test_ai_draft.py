import json
from datetime import timedelta
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_client
from app.core.config import Settings
from app.core.time import local_today
from app.main import app
from app.models.enums import DutyStatus
from app.services.ai_draft_service import AnthropicProvider, GroqProvider, build_provider
from tests.factories import auth, make_officer, make_station, make_user

COMPLAINT = {"text": "Lost my wallet with my NID card near Zindabazar yesterday evening."}
GOOD_DRAFT = {
    "category": "lost_document",
    "title": "Lost wallet with NID card",
    "details": "My wallet containing my national ID card was lost near Zindabazar.",
    "incident_date": (local_today() - timedelta(days=1)).isoformat(),
}


def use(provider) -> None:
    app.dependency_overrides[get_ai_client] = lambda: provider


async def draft(client: AsyncClient, user, body=COMPLAINT):
    return await client.post("/gds/ai-draft", json=body, headers=auth(user))


# --- Groq (default free provider), faked at the HTTP layer -------------------------------


def groq(handler) -> tuple[GroqProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    provider = GroqProvider("gsk_test", "llama-3.3-70b-versatile", 5.0, httpx.MockTransport(record))
    return provider, seen


def groq_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_groq_returns_validated_draft(client: AsyncClient, db_session: AsyncSession) -> None:
    provider, seen = groq(lambda _: groq_reply(json.dumps(GOOD_DRAFT)))
    use(provider)

    response = await draft(client, await make_user(db_session))

    assert response.status_code == 200
    assert response.json() == GOOD_DRAFT
    sent = json.loads(seen[0].content)
    assert seen[0].url.path == "/openai/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer gsk_test"
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["model"] == "llama-3.3-70b-versatile"
    assert "Zindabazar" in sent["messages"][1]["content"]
    assert f"Today is {local_today().isoformat()}" in sent["messages"][1]["content"]


async def test_future_date_is_dropped(client: AsyncClient, db_session: AsyncSession) -> None:
    future = {**GOOD_DRAFT, "incident_date": (local_today() + timedelta(days=3)).isoformat()}
    provider, _ = groq(lambda _: groq_reply(json.dumps(future)))
    use(provider)

    response = await draft(client, await make_user(db_session))

    assert response.json()["incident_date"] is None


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        lambda _: httpx.Response(429, json={"error": {"message": "rate limited"}}),
        lambda _: httpx.Response(500, text="boom"),
        lambda _: httpx.Response(200, json={"unexpected": True}),
        lambda _: groq_reply("not json"),
        lambda _: groq_reply(json.dumps({**GOOD_DRAFT, "category": "murder"})),
        raise_timeout,
    ],
    ids=["rate_limited", "server_error", "odd_shape", "not_json", "bad_category", "timeout"],
)
async def test_groq_failures_are_503(
    client: AsyncClient, db_session: AsyncSession, handler
) -> None:
    provider, _ = groq(handler)
    use(provider)

    response = await draft(client, await make_user(db_session))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_UNAVAILABLE"


# --- Anthropic (alternative provider) ------------------------------------------------------


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


async def test_anthropic_returns_validated_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    fake = FakeClaude(text=json.dumps(GOOD_DRAFT))
    use(AnthropicProvider(fake, "claude-opus-5-5"))

    response = await draft(client, await make_user(db_session))

    assert response.json() == GOOD_DRAFT
    sent = fake.requests[0]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["fallbacks"] == "default"


def timeout_error() -> Exception:
    return anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com"))


@pytest.mark.parametrize(
    "fake",
    [
        FakeClaude(text=None),
        FakeClaude(text="{}", stop_reason="refusal"),
        FakeClaude(error=timeout_error()),
    ],
    ids=["no_text", "refusal", "timeout"],
)
async def test_anthropic_failures_are_503(
    client: AsyncClient, db_session: AsyncSession, fake
) -> None:
    use(AnthropicProvider(fake, "claude-opus-5-5"))

    response = await draft(client, await make_user(db_session))

    assert response.status_code == 503


# --- wiring --------------------------------------------------------------------------------


async def test_no_provider_configured_is_503(client: AsyncClient, db_session: AsyncSession) -> None:
    use(None)

    response = await draft(client, await make_user(db_session))

    assert response.status_code == 503


async def test_provider_choice() -> None:
    assert build_provider(Settings(groq_api_key=None, anthropic_api_key=None)) is None
    both = build_provider(Settings(groq_api_key="g", anthropic_api_key="a"))
    assert isinstance(both, GroqProvider)
    await both.aclose()
    forced = build_provider(
        Settings(ai_provider="anthropic", groq_api_key="g", anthropic_api_key="a")
    )
    assert isinstance(forced, AnthropicProvider)
    await forced.aclose()


async def test_only_citizens_and_text_is_validated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    provider, _ = groq(lambda _: groq_reply(json.dumps(GOOD_DRAFT)))
    use(provider)
    officer = await make_officer(db_session, await make_station(db_session), DutyStatus.AVAILABLE)

    assert (await draft(client, officer.user)).status_code == 403
    assert (await draft(client, await make_user(db_session), {"text": "hi"})).status_code == 422


def test_hosted_postgres_urls_get_asyncpg_driver() -> None:
    settings = Settings(database_url="postgres://u:p@host:5432/db")

    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_neon_url_options_are_translated_for_asyncpg() -> None:
    neon = "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require"

    settings = Settings(database_url=neon)

    assert settings.database_url == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"
