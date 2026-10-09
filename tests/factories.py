"""Insert rows directly for test setup, so each test only exercises the endpoint it is about."""

from datetime import UTC, datetime, timedelta
from itertools import count

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.enums import DutyStatus, UserRole
from app.models.officer import Officer
from app.models.station import Station
from app.models.user import User

PASSWORD = "strongpass123"
_seq = count(1)


def next_phone() -> str:
    return f"+88017{next(_seq):08d}"


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id).token}"}


async def make_station(db: AsyncSession, code: str = "KOT", **overrides) -> Station:
    fields = {
        "name": f"Station {code}",
        "code": code,
        "city": "Sylhet",
        "city_code": "SYL",
        "lat": 24.8949,
        "lng": 91.8687,
    }
    station = Station(**{**fields, **overrides})
    db.add(station)
    await db.flush()
    return station


async def make_user(
    db: AsyncSession,
    role: UserRole = UserRole.CITIZEN,
    station: Station | None = None,
    **overrides,
) -> User:
    fields = {
        "name": f"Test {role.value}",
        "phone": next_phone(),
        "password_hash": hash_password(PASSWORD),
        "role": role,
        "station_id": station.id if station else None,
    }
    user = User(**{**fields, **overrides})
    db.add(user)
    await db.flush()
    return user


async def make_officer(
    db: AsyncSession,
    station: Station,
    duty_status: DutyStatus = DutyStatus.OFF_DUTY,
    located: bool = False,
    lat: float = 24.9,
    lng: float = 91.87,
    seen_minutes_ago: float = 0,
) -> Officer:
    user = await make_user(db, UserRole.OFFICER)
    officer = Officer(
        user=user,
        station_id=station.id,
        badge_no=f"B-{user.id}",
        rank="Constable",
        duty_status=duty_status,
        last_lat=lat if located else None,
        last_lng=lng if located else None,
        last_seen_at=(datetime.now(UTC) - timedelta(minutes=seen_minutes_ago) if located else None),
    )
    db.add(officer)
    await db.flush()
    return officer
