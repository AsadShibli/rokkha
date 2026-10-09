"""Password hashing. JWT helpers are added on Day 2.

bcrypt is deliberately slow (CPU-bound), so these functions are sync and the services call them
through a worker thread. Calling them directly inside an async route would block the event loop
for every other request.
"""

import bcrypt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
