from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    # No format check here: a badly formatted phone is just "wrong credentials" (401).
    phone: str = Field(min_length=1, max_length=20, examples=["+8801711000000"])
    password: str = Field(min_length=1, max_length=200, examples=["strongpass123"])


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds", examples=[900])
