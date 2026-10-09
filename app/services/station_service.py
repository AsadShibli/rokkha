from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.errors import commit_or_conflict, taken
from app.models.enums import UserRole
from app.models.station import Station
from app.models.user import User
from app.repositories.station_repository import StationRepository
from app.schemas.common import PageParams
from app.schemas.station import StationCreate
from app.schemas.user import UserCreate
from app.services.user_service import UserService


class StationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.stations = StationRepository(session)
        self.accounts = UserService(session)

    async def list(self, params: PageParams, city: str | None) -> tuple[Sequence[Station], int]:
        return await self.stations.list(params, city)

    async def create(self, data: StationCreate) -> Station:
        """BR Stations 1-2: code unique and immutable; name unique within the city."""
        clashes = []
        if await self.stations.exists_code(data.code):
            clashes.append(taken("code"))
        if await self.stations.exists_name_in_city(data.city, data.name):
            clashes.append(taken("name"))
        if clashes:
            raise ConflictError(details=clashes)
        station = Station(**data.model_dump())
        self.stations.add(station)
        await commit_or_conflict(self.session)
        return station

    async def create_admin(self, station_id: int, data: UserCreate) -> User:
        """BR Stations 3: only a super admin creates station admins, bound to one station."""
        station = await self.stations.get(station_id)
        if station is None:
            raise NotFoundError("Station not found.")
        clashes = await self.accounts.taken_fields(data.phone, data.email)
        if clashes:
            raise ConflictError(details=clashes)
        user = await self.accounts.build_account(data, UserRole.STATION_ADMIN, station.id)
        await commit_or_conflict(self.session)
        return user
