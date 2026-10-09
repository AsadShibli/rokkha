from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import GdCategory, GdStatus, sql_in
from app.models.types import str_enum


class Gd(IdMixin, TimestampMixin, Base):
    """Online General Diary entry."""

    __tablename__ = "gds"
    __table_args__ = (
        UniqueConstraint("gd_number"),
        CheckConstraint(f"category IN ({sql_in(GdCategory)})", name="category_valid"),
        CheckConstraint(f"status IN ({sql_in(GdStatus)})", name="status_valid"),
        CheckConstraint(
            "status NOT IN ('approved', 'rejected') "
            "OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="final_is_reviewed",
        ),
        CheckConstraint("status <> 'rejected' OR review_note IS NOT NULL", name="reject_has_note"),
        Index("ix_gds_citizen_id_created_at", "citizen_id", "created_at"),
        Index("ix_gds_station_id_status_created_at", "station_id", "status", "created_at"),
    )

    gd_number: Mapped[str] = mapped_column(String(30))
    citizen_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    station_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stations.id", ondelete="RESTRICT")
    )
    category: Mapped[GdCategory] = mapped_column(str_enum(GdCategory, 20))
    title: Mapped[str] = mapped_column(String(150))
    details: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[date] = mapped_column(Date)
    status: Mapped[GdStatus] = mapped_column(
        str_enum(GdStatus, 15), server_default=GdStatus.SUBMITTED.value
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(1000))


class GdSequence(Base):
    """Per-station, per-year counter behind GD numbers."""

    __tablename__ = "gd_sequences"
    __table_args__ = (CheckConstraint("last_value >= 0", name="last_value_non_negative"),)

    station_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stations.id", ondelete="RESTRICT"), primary_key=True
    )
    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, server_default="0")
