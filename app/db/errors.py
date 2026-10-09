import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ActiveSosExistsError, AppError, ConflictError

_CONSTRAINT_IN_MESSAGE = re.compile(r'constraint "([^"]+)"')

# Unique constraint -> the request field it protects (names come from the naming convention).
UNIQUE_FIELDS = {
    "uq_users_phone": "phone",
    "uq_users_email": "email",
    "uq_stations_code": "code",
    "uq_stations_city_name": "name",
    "uq_officers_badge_no": "badge_no",
}

# Constraints that encode a business rule rather than a duplicate field.
RULE_ERRORS: dict[str, type[AppError]] = {
    "uq_incidents_open_sos_per_citizen": ActiveSosExistsError,
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


def _mapped_error(exc: IntegrityError) -> AppError | None:
    name = constraint_name(exc) or ""
    if name in RULE_ERRORS:
        return RULE_ERRORS[name]()
    if name in UNIQUE_FIELDS:
        return ConflictError(details=[taken(UNIQUE_FIELDS[name])])
    return None


async def _write_or_conflict(session: AsyncSession, *, commit: bool) -> None:
    try:
        await (session.commit() if commit else session.flush())
    except IntegrityError as exc:
        await session.rollback()
        error = _mapped_error(exc)
        if error is None:
            raise
        raise error from exc


async def commit_or_conflict(session: AsyncSession) -> None:
    """Commit; turn a known constraint violation into the matching 409.

    Services pre-check rules for a friendly error, but two requests can race past that check.
    The database constraint is the real guarantee; this maps its error back to the API.
    """
    await _write_or_conflict(session, commit=True)


async def flush_or_conflict(session: AsyncSession) -> None:
    """Same as commit_or_conflict, for when the INSERT must hit the DB mid-transaction."""
    await _write_or_conflict(session, commit=False)
