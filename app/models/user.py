from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import UserRole, sql_in
from app.models.types import str_enum

if TYPE_CHECKING:
    from app.models.officer import Officer

PHONE_PATTERN = r"^\+8801[3-9][0-9]{8}$"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone"),
        UniqueConstraint("email"),
        CheckConstraint(f"phone ~ '{PHONE_PATTERN}'", name="phone_format"),
        CheckConstraint(f"role IN ({sql_in(UserRole)})", name="role_valid"),
        # A station admin must have a station, and nobody else may have one.
        CheckConstraint(
            "(role = 'station_admin') = (station_id IS NOT NULL)", name="station_admin_station"
        ),
    )

    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(14))
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, 20), server_default=UserRole.CITIZEN.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    station_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stations.id", ondelete="RESTRICT"), index=True
    )

    officer: Mapped["Officer | None"] = relationship(back_populates="user", lazy="raise")
