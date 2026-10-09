import re

from sqlalchemy.exc import IntegrityError

_CONSTRAINT_IN_MESSAGE = re.compile(r'constraint "([^"]+)"')


def constraint_name(exc: IntegrityError) -> str | None:
    """Name of the violated constraint, e.g. "uq_users_phone"."""
    # asyncpg's exception (wrapped twice by SQLAlchemy) carries the name directly.
    driver_error = getattr(exc.orig, "__cause__", None)
    name = getattr(driver_error, "constraint_name", None)
    if name:
        return name
    match = _CONSTRAINT_IN_MESSAGE.search(str(exc.orig))
    return match.group(1) if match else None
