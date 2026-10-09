from enum import StrEnum


class UserRole(StrEnum):
    CITIZEN = "citizen"
    OFFICER = "officer"
    STATION_ADMIN = "station_admin"
    SUPER_ADMIN = "super_admin"


class DutyStatus(StrEnum):
    OFF_DUTY = "off_duty"
    AVAILABLE = "available"
    BUSY = "busy"


def sql_in(enum: type[StrEnum]) -> str:
    """SQL list like 'a', 'b' for CHECK constraints, so allowed values live only in the enum."""
    return ", ".join(f"'{member.value}'" for member in enum)
