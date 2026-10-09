from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import IncidentStatus, IncidentType, sql_in
from app.models.officer import Officer
from app.models.types import str_enum

_OPEN = "status IN ('pending', 'assigned', 'en_route')"
_ACTIVE = "status IN ('assigned', 'en_route')"


class Incident(IdMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(f"type IN ({sql_in(IncidentType)})", name="type_valid"),
        CheckConstraint(f"status IN ({sql_in(IncidentStatus)})", name="status_valid"),
        # pending <=> no officer (cancelled may or may not have had one).
        CheckConstraint(
            "status = 'cancelled' OR (status = 'pending') = (officer_id IS NULL)",
            name="officer_matches_status",
        ),
        CheckConstraint("status <> 'resolved' OR resolved_at IS NOT NULL", name="resolved_at_set"),
        CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL", name="cancelled_at_set"
        ),
        CheckConstraint("lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="lng_range"),
        # BR Incidents-creation 7: one open SOS per citizen, enforced by the database.
        Index(
            "uq_incidents_open_sos_per_citizen",
            "citizen_id",
            unique=True,
            postgresql_where=f"type = 'sos' AND {_OPEN}",
        ),
        # An officer never holds two active incidents, even if a service has a bug.
        Index(
            "uq_incidents_active_per_officer",
            "officer_id",
            unique=True,
            postgresql_where=_ACTIVE,
        ),
        Index("ix_incidents_citizen_id_created_at", "citizen_id", "created_at"),
        Index("ix_incidents_officer_id_created_at", "officer_id", "created_at"),
        Index("ix_incidents_station_id_status_created_at", "station_id", "status", "created_at"),
    )

    citizen_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    officer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("officers.id", ondelete="RESTRICT")
    )
    station_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stations.id", ondelete="RESTRICT")
    )
    type: Mapped[IncidentType] = mapped_column(str_enum(IncidentType, 10))
    status: Mapped[IncidentStatus] = mapped_column(
        str_enum(IncidentStatus, 12), server_default=IncidentStatus.PENDING.value
    )
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    officer: Mapped[Officer | None] = relationship(lazy="joined")
    events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident",
        lazy="raise",
        order_by="(IncidentEvent.created_at, IncidentEvent.id)",
        cascade="all, delete-orphan",
    )


class IncidentEvent(IdMixin, TimestampMixin, Base):
    """Append-only audit trail: one row per status change."""

    __tablename__ = "incident_events"
    __table_args__ = (
        CheckConstraint(f"to_status IN ({sql_in(IncidentStatus)})", name="to_status_valid"),
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({sql_in(IncidentStatus)})",
            name="from_status_valid",
        ),
        Index("ix_incident_events_incident_id_created_at", "incident_id", "created_at"),
    )

    incident_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("incidents.id", ondelete="CASCADE")
    )
    # NULL actor = the system did it (auto-assign, escalation).
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    officer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("officers.id", ondelete="RESTRICT"), index=True
    )
    from_status: Mapped[IncidentStatus | None] = mapped_column(str_enum(IncidentStatus, 12))
    to_status: Mapped[IncidentStatus] = mapped_column(str_enum(IncidentStatus, 12))
    note: Mapped[str | None] = mapped_column(String(500))

    incident: Mapped[Incident] = relationship(back_populates="events", lazy="raise")
