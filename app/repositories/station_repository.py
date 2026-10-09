from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.station import Station
from app.repositories.base import paginate
from app.schemas.common import PageParams
from app.services.geo import haversine_km


class StationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, station_id: int) -> Station | None:
        return await self.session.get(Station, station_id)

    async def exists_code(self, code: str) -> bool:
        return await self.session.scalar(select(Station.id).where(Station.code == code)) is not None

    async def exists_name_in_city(self, city: str, name: str) -> bool:
        stmt = select(Station.id).where(Station.city == city, Station.name == name)
        return await self.session.scalar(stmt) is not None

    async def list(
        self, params: PageParams, city: str | None = None
    ) -> tuple[Sequence[Station], int]:
        stmt = select(Station).order_by(Station.name, Station.id)
        if city:
            stmt = stmt.where(func.lower(Station.city) == city.lower())
        return await paginate(self.session, stmt, params)

    async def nearest(self, lat: float, lng: float) -> Station | None:
        """Jurisdiction of a location = the nearest station (BR Incidents-creation 2)."""
        stmt = (
            select(Station)
            .order_by(haversine_km(Station.lat, Station.lng, lat, lng), Station.id)
            .limit(1)
        )
        return await self.session.scalar(stmt)

    def add(self, station: Station) -> None:
        self.session.add(station)
