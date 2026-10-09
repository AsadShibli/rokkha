"""Demo data: a super admin, 3 Dhaka stations with admins, 6 officers, 5 citizens.

    uv run python -m scripts.seed            # create (refuses if already seeded)
    uv run python -m scripts.seed --touch    # mark seeded on-duty officers as seen now

Officers count as reachable only if seen in the last 10 minutes, so run --touch right before
a demo (or have the officers send PATCH /officers/me/location).
"""

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.enums import DutyStatus, UserRole
from app.models.officer import Officer
from app.models.station import Station
from app.models.user import User

PASSWORD = "rokkha1234"  # demo only: every seeded account uses it
SUPER_ADMIN_PHONE = "+8801711000000"

# name, code, lat, lng; one admin per station.
STATIONS = [
    ("Gulshan", "GUL", 23.7808, 90.4150),
    ("Badda", "BAD", 23.7806, 90.4265),
    ("Tejgaon", "TEJ", 23.7639, 90.3925),
]
# station code, name, rank, on duty?, lat, lng
# Demo: an SOS at Gulshan 1 (23.7810, 90.4140) goes to the Badda officer, who is closer.
OFFICERS = [
    ("GUL", "Rafiq Islam", "Sub-Inspector", True, 23.7950, 90.4050),
    ("GUL", "Sadia Rahman", "Constable", False, None, None),
    ("BAD", "Tanvir Hasan", "Sub-Inspector", True, 23.7812, 90.4180),
    ("BAD", "Nusrat Jahan", "Constable", False, None, None),
    ("TEJ", "Mahmud Karim", "Inspector", True, 23.7650, 90.3940),
    ("TEJ", "Farhana Akter", "Constable", False, None, None),
]
CITIZENS = ["Ayesha Siddiqua", "Imran Hossain", "Mitu Das", "Shafiq Ahmed", "Lamia Chowdhury"]


async def seed() -> None:
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).where(User.phone == SUPER_ADMIN_PHONE)):
            print("Already seeded. Use --touch to refresh officer locations.")
            return
        pw = await asyncio.to_thread(hash_password, PASSWORD)
        now = datetime.now(UTC)

        db.add(
            User(
                name="Control Room",
                phone=SUPER_ADMIN_PHONE,
                password_hash=pw,
                role=UserRole.SUPER_ADMIN,
            )
        )
        stations = {}
        for i, (name, code, lat, lng) in enumerate(STATIONS, start=1):
            station = Station(name=name, code=code, city="Dhaka", city_code="DHA", lat=lat, lng=lng)
            db.add(station)
            await db.flush()
            stations[code] = station
            db.add(
                User(
                    name=f"OC {name}",
                    phone=f"+88017110000{i:02d}",
                    password_hash=pw,
                    role=UserRole.STATION_ADMIN,
                    station_id=station.id,
                )
            )
        for i, (code, name, rank, on_duty, lat, lng) in enumerate(OFFICERS, start=1):
            user = User(
                name=name, phone=f"+88017220000{i:02d}", password_hash=pw, role=UserRole.OFFICER
            )
            db.add(
                Officer(
                    user=user,
                    station_id=stations[code].id,
                    badge_no=f"{code}-{100 + i}",
                    rank=rank,
                    duty_status=DutyStatus.AVAILABLE if on_duty else DutyStatus.OFF_DUTY,
                    last_lat=lat,
                    last_lng=lng,
                    last_seen_at=now if on_duty else None,
                )
            )
        for i, name in enumerate(CITIZENS, start=1):
            db.add(User(name=name, phone=f"+88017330000{i:02d}", password_hash=pw))
        await db.commit()

    print(f"Seeded. Password for every account: {PASSWORD}")
    print(f"  super admin    {SUPER_ADMIN_PHONE}")
    for i, (name, *_rest) in enumerate(STATIONS, start=1):
        print(f"  station admin  +88017110000{i:02d}  ({name})")
    for i, (code, name, *_rest) in enumerate(OFFICERS, start=1):
        print(f"  officer        +88017220000{i:02d}  ({name}, {code})")
    for i, name in enumerate(CITIZENS, start=1):
        print(f"  citizen        +88017330000{i:02d}  ({name})")


async def touch() -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            update(Officer)
            .where(Officer.duty_status == DutyStatus.AVAILABLE, Officer.last_lat.is_not(None))
            .values(last_seen_at=datetime.now(UTC))
        )
        await db.commit()
    print(f"Marked {result.rowcount} on-duty officer(s) as seen now.")


async def main(args: argparse.Namespace) -> None:
    await (touch() if args.touch else seed())
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument(
        "--touch", action="store_true", help="refresh on-duty officers' last_seen_at"
    )
    asyncio.run(main(parser.parse_args()))
