"""Turn a free-text complaint (Bangla or English) into a suggested GD draft with Claude.

The draft is only a suggestion for the citizen to edit: nothing is saved, and the model's
output is validated with the same field rules as POST /gds before it is returned.
"""

import logging
from datetime import date

import anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import get_settings
from app.core.exceptions import AiUnavailableError
from app.core.time import local_today
from app.models.enums import GdCategory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You help citizens of Bangladesh fill in an Online General Diary (GD) form for their local "
    "station. Read the complaint and produce a draft with: a category, a short title "
    "(5-150 characters), clear factual details (20-5000 characters) and the date the incident "
    "happened. Write the title and details in the same language as the complaint (Bangla or "
    "English). Keep only facts the citizen stated; never invent names, places, times or items. "
    "Resolve relative dates such as 'yesterday' or 'gotokal' against today's date. If the date "
    "is not stated or can't be worked out, use null. Pick category 'other' when nothing else fits."
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


class GdDraftService:
    def __init__(self, client: anthropic.AsyncAnthropic | None):
        self.client = client

    async def draft(self, text: str) -> GdDraftOut:
        if self.client is None:
            raise AiUnavailableError("AI drafting is not configured on this server.")
        settings = get_settings()
        try:
            response = await self.client.beta.messages.create(
                model=settings.ai_model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Today is {local_today().isoformat()}.\n\nComplaint:\n{text}",
                    }
                ],
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
            logger.warning("AI draft: Claude unreachable or timed out: %s", exc)
            raise AiUnavailableError() from exc
        except anthropic.APIStatusError as exc:
            logger.warning(
                "AI draft: Claude API error %s (request %s)",
                exc.status_code,
                getattr(exc, "request_id", None),
            )
            raise AiUnavailableError() from exc

        if response.stop_reason == "refusal":
            logger.info("AI draft: request declined (%s)", response.stop_details)
            raise AiUnavailableError("Couldn't draft this one; please fill in the form yourself.")
        body = next((b.text for b in response.content if b.type == "text"), None)
        if body is None:
            raise AiUnavailableError()
        try:
            return GdDraftOut.model_validate_json(body)
        except ValidationError as exc:
            logger.warning("AI draft: output failed validation: %s", exc.errors())
            raise AiUnavailableError() from exc
