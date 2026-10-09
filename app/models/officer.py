from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import DutyStatus, sql_in
from app.models.types import str_enum
from app.models.user import User


class Officer(IdMixin, TimestampMixin, Base):
    __tablename__ = "officers"
    __table_args__ = (
        UniqueConstraint("user_id"),
        UniqueConstraint("badge_no"),
        CheckConstraint(f"duty_status IN ({sql_in(DutyStatus)})", name="duty_status_valid"),
        CheckConstraint("(last_lat IS NULL) = (last_lng IS NULL)", name="location_pair"),
        CheckConstraint("last_lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("last_lng BETWEEN -180 AND 180", name="lng_range"),
        Index("ix_officers_station_id_duty_status", "station_id", "duty_status"),
        # The nearest-officer search only ever looks at available officers.
        Index(
            "ix_officers_available_last_seen_at",
            "last_seen_at",
            postgresql_where="duty_status = 'available'",
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    station_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stations.id", ondelete="RESTRICT")
    )
    badge_no: Mapped[str] = mapped_column(String(20))
    rank: Mapped[str] = mapped_column(String(40))
    duty_status: Mapped[DutyStatus] = mapped_column(
        str_enum(DutyStatus, 10), server_default=DutyStatus.OFF_DUTY.value
    )
    last_lat: Mapped[float | None] = mapped_column(Float)
    last_lng: Mapped[float | None] = mapped_column(Float)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Always needed to show the officer's name, so load it in the same query. INNER JOIN
    # (user_id is NOT NULL), which also lets FOR UPDATE OF officers work on the query.
    user: Mapped[User] = relationship(back_populates="officer", lazy="joined", innerjoin=True)
