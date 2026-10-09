from datetime import date, datetime
from zoneinfo import ZoneInfo

# Calendar rules (GD year, "not in the future") follow the local day, not UTC.
LOCAL_TZ = ZoneInfo("Asia/Dhaka")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def local_today() -> date:
    return local_now().date()
