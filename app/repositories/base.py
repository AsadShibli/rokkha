from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import PageParams


async def paginate[T](
    session: AsyncSession, stmt: Select[tuple[T]], params: PageParams
) -> tuple[Sequence[T], int]:
    """Run one page of `stmt` (already filtered and ordered) plus a total count."""
    count_stmt: Select[Any] = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = await session.scalar(count_stmt) or 0
    items = (await session.scalars(stmt.offset(params.offset).limit(params.page_size))).all()
    return items, total
