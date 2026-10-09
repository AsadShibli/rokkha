from pydantic import BaseModel, Field


class DashboardOut(BaseModel):
    station_id: int | None = Field(description="null = city-wide")
    incidents: dict[str, int] = Field(examples=[{"pending": 1, "assigned": 2, "resolved": 40}])
    open_sos: int
    gds: dict[str, int]
    officers: dict[str, int]
    avg_response_seconds_7d: int | None = Field(
        description="Mean created -> accepted time for incidents accepted in the last 7 days"
    )
