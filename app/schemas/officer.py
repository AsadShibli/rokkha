from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DutyStatus
from app.schemas.common import Latitude, Longitude
from app.schemas.user import UserBrief, UserCreate


class OfficerCreate(UserCreate):
    """Station admin creates the officer's account and profile together.

    `station_id` and `duty_status` are not accepted: the station is the admin's own and new
    officers start off duty (BR Officers 1, 4).
    """

    badge_no: str = Field(min_length=2, max_length=20, examples=["KOT-1043"])
    rank: str = Field(min_length=2, max_length=40, examples=["Sub-Inspector"])


class OfficerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user: UserBrief
    station_id: int
    badge_no: str
    rank: str
    duty_status: DutyStatus
    last_lat: float | None
    last_lng: float | None
    last_seen_at: datetime | None


class OfficerStatusIn(BaseModel):
    # "busy" is set only by the system (BR Officers 5), so it is not a valid input here.
    duty_status: Literal["available", "off_duty"]


class LocationIn(BaseModel):
    lat: Latitude
    lng: Longitude
