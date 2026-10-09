import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError

_CONSTRAINT_IN_MESSAGE = re.compile(r'constraint "([^"]+)"')

# Unique constraint -> the request field it protects (names come from the naming convention).
UNIQUE_FIELDS = {
    "uq_users_phone": "phone",
    "uq_users_email": "email",
    "uq_stations_code": "code",
    "uq_stations_city_name": "name",
    "uq_officers_badge_no": "badge_no",
}


def constraint_name(exc: IntegrityError) -> str | None:
    """Name of the violated constraint, e.g. "uq_users_phone"."""
    # asyncpg's exception (wrapped twice by SQLAlchemy) carries the name directly.
    driver_error = getattr(exc.orig, "__cause__", None)
    name = getattr(driver_error, "constraint_name", None)
    if name:
        return name
    match = _CONSTRAINT_IN_MESSAGE.search(str(exc.orig))
    return match.group(1) if match else None


def taken(field: str) -> dict[str, str]:
    return {"field": field, "message": f"This {field} is already in use"}


async def commit_or_conflict(session: AsyncSession) -> None:
    """Commit; turn a unique-constraint violation into 409 CONFLICT naming the field.

    Services pre-check uniqueness for a friendly error, but two requests can race past that
    check. The database constraint is the real guarantee; this maps its error back to the API.
    """
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        field = UNIQUE_FIELDS.get(constraint_name(exc) or "")
        if field is None:
            raise
        raise ConflictError(details=[taken(field)]) from exc
