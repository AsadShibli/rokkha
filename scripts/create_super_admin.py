"""Create a super admin (there is deliberately no API endpoint for this).

    uv run python -m scripts.create_super_admin --name "Control Room" --phone +8801700000000

The password is asked interactively (or read from SUPER_ADMIN_PASSWORD), so it never lands
in shell history.
"""

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import ValidationError

from app.db.errors import commit_or_conflict
from app.db.session import SessionLocal, engine
from app.models.enums import UserRole
from app.schemas.user import UserCreate
from app.services.user_service import UserService


async def create(data: UserCreate) -> int:
    async with SessionLocal() as session:
        accounts = UserService(session)
        if clashes := await accounts.taken_fields(data.phone, data.email):
            raise SystemExit(f"Already in use: {', '.join(c['field'] for c in clashes)}")
        user = await accounts.build_account(data, UserRole.SUPER_ADMIN)
        await commit_or_conflict(session)
        user_id = user.id
    await engine.dispose()
    return user_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone", required=True, help="+8801XXXXXXXXX")
    parser.add_argument("--email")
    args = parser.parse_args()

    password = os.environ.get("SUPER_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        data = UserCreate(name=args.name, phone=args.phone, email=args.email, password=password)
    except ValidationError as exc:
        sys.exit(f"Invalid input:\n{exc}")

    user_id = asyncio.run(create(data))
    print(f"Super admin created (id={user_id}).")


if __name__ == "__main__":
    main()
