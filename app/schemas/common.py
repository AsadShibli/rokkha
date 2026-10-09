from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

# Bangladesh bounding box (BR Locations 1). The DB only checks the global range.
Latitude = Annotated[float, Field(ge=20.5, le=26.7, examples=[24.8949])]
Longitude = Annotated[float, Field(ge=88.0, le=92.7, examples=[91.8687])]


class PageParams(BaseModel):
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
