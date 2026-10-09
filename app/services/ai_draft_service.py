"""Turn a free-text complaint (Bangla or English) into a suggested GD draft with an LLM.

Two providers: Groq (free tier, OpenAI-compatible HTTP API) and Anthropic. The draft is only a
suggestion for the citizen to edit: nothing is saved, and the model's output is validated with
the same field rules as POST /gds before it is returned. Any provider problem becomes
503 AI_UNAVAILABLE so the citizen can fill the form by hand.
"""

import logging
from datetime import date
from typing import Protocol

import anthropic
import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import Settings
from app.core.exceptions import AiUnavailableError
from app.core.time import local_today
from app.models.enums import GdCategory

logger = logging.getLogger(__name__)

CATEGORIES = ", ".join(c.value for c in GdCategory)
SYSTEM_PROMPT = (
    "You help citizens of Bangladesh fill in an Online General Diary (GD) form for their local "
    "station. Read the complaint and produce a draft with: a category, a short title "
    "(5-150 characters), clear factual details (20-5000 characters) and the date the incident "
    "happened. Write the title and details in the same language as the complaint (Bangla or "
    "English). Keep only facts the citizen stated; never invent names, places, times or items. "
    "Resolve relative dates such as 'yesterday' or 'gotokal' against today's date. If the date "
    "is not stated or can't be worked out, use null. Pick category 'other' when nothing else "
    "fits.\n\n"
    "Reply with only a JSON object with exactly these keys: "
    f'"category" (one of: {CATEGORIES}), "title", "details", '
    '"incident_date" (YYYY-MM-DD or null).'
)

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": [c.value for c in GdCategory]},
        "title": {"type": "string"},
        "details": {"type": "string"},
        "incident_date": {
            "type": ["string", "null"],
            "description": "YYYY-MM-DD, or null if unknown",
        },
    },
    "required": ["category", "title", "details", "incident_date"],
    "additionalProperties": False,
}


class GdDraftIn(BaseModel):
    text: str = Field(
        min_length=10,
        max_length=2000,
        examples=["গতকাল সন্ধ্যায় জিন্দাবাজারে আমার মানিব্যাগ হারিয়ে গেছে, ভিতরে NID কার্ড ছিল।"],
    )


class GdDraftOut(BaseModel):
    """Same limits as GdCreate, minus the station (the citizen picks that)."""

    category: GdCategory
    title: str = Field(min_length=5, max_length=150)
    details: str = Field(min_length=20, max_length=5000)
    incident_date: date | None

    @field_validator("incident_date")
    @classmethod
    def drop_future_dates(cls, value: date | None) -> date | None:
        # A future date would fail POST /gds; better to leave it for the citizen to fill in.
        return value if value is None or value <= local_today() else None


def user_message(text: str) -> str:
    return f"Today is {local_today().isoformat()}.\n\nComplaint:\n{text}"


class DraftProvider(Protocol):
    async def complete(self, text: str) -> str:
        """Return the model's raw JSON text, or raise AiUnavailableError."""
        ...

    async def aclose(self) -> None: ...


class GroqProvider:
    """Groq's OpenAI-compatible chat completions API (free tier, no card)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.model = model
        self.http = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def complete(self, text: str) -> str:
        try:
            response = await self.http.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message(text)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 1500,
                },
            )
        except httpx.HTTPError as exc:
            logger.warning("AI draft: Groq unreachable or timed out: %s", exc)
            raise AiUnavailableError() from exc
        if response.status_code != 200:
            logger.warning("AI draft: Groq error %s: %s", response.status_code, response.text[:200])
            raise AiUnavailableError()
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AiUnavailableError() from exc

    async def aclose(self) -> None:
        await self.http.aclose()


class AnthropicProvider:
    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self.client = client
        self.model = model

    async def complete(self, text: str) -> str:
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message(text)}],
                # A simple extraction: low effort keeps it fast and cheap.
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": DRAFT_SCHEMA},
                },
                # If a safety classifier declines, the API retries on its recommended model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            logger.warning("AI draft: Anthropic unreachable or timed out: %s", exc)
            raise AiUnavailableError() from exc
        except anthropic.APIStatusError as exc:
            logger.warning("AI draft: Anthropic API error %s", exc.status_code)
            raise AiUnavailableError() from exc
        if response.stop_reason == "refusal":
            logger.info("AI draft: request declined (%s)", response.stop_details)
            raise AiUnavailableError("Couldn't draft this one; please fill in the form yourself.")
        body = next((b.text for b in response.content if b.type == "text"), None)
        if body is None:
            raise AiUnavailableError()
        return body

    async def aclose(self) -> None:
        await self.client.close()


def build_provider(settings: Settings) -> DraftProvider | None:
    """AI_PROVIDER=groq|anthropic, or auto: whichever key is set (Groq first)."""
    provider = settings.ai_provider
    if provider == "auto":
        provider = "groq" if settings.groq_api_key else "anthropic"
    if provider == "groq" and settings.groq_api_key:
        return GroqProvider(settings.groq_api_key, settings.groq_model, settings.ai_timeout_seconds)
    if provider == "anthropic" and settings.anthropic_api_key:
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.ai_timeout_seconds,
            max_retries=0,  # the citizen is waiting; fail fast and let them type instead
        )
        return AnthropicProvider(client, settings.ai_model)
    return None


class GdDraftService:
    def __init__(self, provider: DraftProvider | None):
        self.provider = provider

    async def draft(self, text: str) -> GdDraftOut:
        if self.provider is None:
            raise AiUnavailableError("AI drafting is not configured on this server.")
        body = await self.provider.complete(text)
        try:
            return GdDraftOut.model_validate_json(body)
        except ValidationError as exc:
            logger.warning("AI draft: output failed validation: %s", exc.errors())
            raise AiUnavailableError() from exc
