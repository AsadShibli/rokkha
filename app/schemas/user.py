from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.models.user import PHONE_PATTERN

Phone = Annotated[
    str,
    Field(pattern=PHONE_PATTERN, examples=["+8801711000000"], description="+8801XXXXXXXXX"),
]


class UserCreate(BaseModel):
    """Public registration. Unknown fields such as `role` are ignored, never applied."""

    name: str = Field(min_length=2, max_length=100, examples=["Rahim Uddin"])
    phone: Phone
    email: EmailStr | None = Field(default=None, examples=["rahim@example.com"])
    password: str = Field(min_length=8, examples=["strongpass123"])

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters")
        return value

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes; Bangla characters take 3 bytes each.
        if len(value.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
