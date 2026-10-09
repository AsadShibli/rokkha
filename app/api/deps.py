from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

# current_user and require_role(...) arrive with JWT on Day 2.
