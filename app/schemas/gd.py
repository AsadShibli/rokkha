from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import local_today
from app.models.enums import GdCategory, GdStatus


class GdCreate(BaseModel):
    station_id: int
    category: GdCategory
    title: str = Field(min_length=5, max_length=150, examples=["Lost national ID card"])
    details: str = Field(
        min_length=20,
        max_length=5000,
        examples=["Lost my NID card near Zindabazar around 6 pm, inside a brown wallet."],
    )
    incident_date: date

    @field_validator("title", "details")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("incident_date")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > local_today():
            raise ValueError("Incident date cannot be in the future")
        return value


class GdReviewIn(BaseModel):
    action: Literal["start_review", "approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reject_needs_note(self) -> Self:
        if self.action == "reject" and not (self.note and self.note.strip()):
            raise ValueError("A note is required when rejecting")
        return self


class GdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gd_number: str
    citizen_id: int
    station_id: int
    category: GdCategory
    title: str
    details: str
    incident_date: date
    status: GdStatus
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
