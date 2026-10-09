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


class IncidentType(StrEnum):
    SOS = "sos"
    REPORT = "report"


class IncidentStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


OPEN_INCIDENT_STATUSES = (
    IncidentStatus.PENDING,
    IncidentStatus.ASSIGNED,
    IncidentStatus.EN_ROUTE,
)


class GdCategory(StrEnum):
    LOST_ITEM = "lost_item"
    LOST_DOCUMENT = "lost_document"
    MISSING_PERSON = "missing_person"
    THREAT = "threat"
    HARASSMENT = "harassment"
    OTHER = "other"


class GdStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
