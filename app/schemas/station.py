from pydantic import BaseModel, ConfigDict, Field

from app.models.station import CITY_CODE_PATTERN, STATION_CODE_PATTERN
from app.schemas.common import Latitude, Longitude


class StationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Kotwali"])
    code: str = Field(pattern=STATION_CODE_PATTERN, examples=["KOT"])
    city: str = Field(min_length=2, max_length=60, examples=["Sylhet"])
    city_code: str = Field(pattern=CITY_CODE_PATTERN, examples=["SYL"])
    lat: Latitude
    lng: Longitude


class StationBrief(BaseModel):
    """Enough to name a thana in another resource (incident, GD, officer)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    city: str
    city_code: str
    lat: float
    lng: float
