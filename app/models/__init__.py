# Import every model here so Base.metadata is complete for Alembic and tests.
from app.models.user import User

__all__ = ["User"]
