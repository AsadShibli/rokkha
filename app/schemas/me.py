from app.schemas.officer import OfficerOut
from app.schemas.user import UserOut


class MeOut(UserOut):
    """The caller's own profile; officers also get their officer profile."""

    officer: OfficerOut | None = None
