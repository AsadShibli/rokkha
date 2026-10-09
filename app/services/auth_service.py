from anyio import to_thread
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.db.errors import constraint_name
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate

_UNIQUE_FIELDS = {"uq_users_phone": "phone", "uq_users_email": "email"}


def _taken(field: str) -> dict[str, str]:
    return {"field": field, "message": f"This {field} is already registered"}


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        """Create a citizen account (BR Accounts 1-4)."""
        # Check both fields first so the client hears about every clash in one response.
        taken = []
        if await self.users.get_by_phone(data.phone):
            taken.append(_taken("phone"))
        if data.email and await self.users.get_by_email(data.email):
            taken.append(_taken("email"))
        if taken:
            raise ConflictError("Phone or email already registered.", taken)

        password_hash = await to_thread.run_sync(hash_password, data.password)
        user = User(
            name=data.name,
            phone=data.phone,
            email=data.email,
            password_hash=password_hash,
            role=UserRole.CITIZEN,
        )
        try:
            await self.users.add(user)
            await self.session.commit()
        except IntegrityError as exc:
            # Two registrations raced past the check above; the unique constraint decides.
            await self.session.rollback()
            field = _UNIQUE_FIELDS.get(constraint_name(exc) or "")
            if field is None:
                raise
            raise ConflictError("Phone or email already registered.", [_taken(field)]) from exc
        return user
