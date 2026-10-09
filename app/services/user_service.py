from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.errors import taken
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserService:
    """Account creation shared by registration, station admins and officers."""

    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)

    async def taken_fields(self, phone: str, email: str | None) -> list[dict[str, str]]:
        """Fields already used by another account, so one response can list every clash."""
        clashes = []
        if await self.users.get_by_phone(phone):
            clashes.append(taken("phone"))
        if email and await self.users.get_by_email(email):
            clashes.append(taken("email"))
        return clashes

    async def build_account(
        self, data: UserCreate, role: UserRole, station_id: int | None = None
    ) -> User:
        """New, not yet committed user. The caller commits (possibly with more rows)."""
        password_hash = await to_thread.run_sync(hash_password, data.password)
        user = User(
            name=data.name,
            phone=data.phone,
            email=data.email,
            password_hash=password_hash,
            role=role,
            station_id=station_id,
        )
        self.users.add(user)
        return user
