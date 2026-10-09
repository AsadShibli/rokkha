"""Password hashing and JWTs.

bcrypt is deliberately slow (CPU-bound), so the hashing functions are sync and the services call
them through a worker thread. Calling them directly inside an async route would block the event
loop for every other request.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


@lru_cache
def dummy_password_hash() -> str:
    """Checked against when the phone is unknown, so both login failures take the same time."""
    return hash_password("not-a-real-password")


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    jti: uuid.UUID


def _issue(user_id: int, token_type: TokenType, lifetime: timedelta) -> IssuedToken:
    settings = get_settings()
    now = datetime.now(UTC)
    jti = uuid.uuid4()
    expires_at = now + lifetime
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(jti),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(user_id: int) -> IssuedToken:
    return _issue(user_id, "access", timedelta(minutes=get_settings().access_token_minutes))


def create_refresh_token(user_id: int) -> IssuedToken:
    return _issue(user_id, "refresh", timedelta(days=get_settings().refresh_token_days))


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    """Verify signature, expiry and token type. Raises InvalidTokenError on any problem."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "exp"]},
        )
        if payload["type"] != expected_type:
            raise InvalidTokenError()
        return TokenClaims(user_id=int(payload["sub"]), jti=uuid.UUID(payload["jti"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError() from exc
