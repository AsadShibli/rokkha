from sqlalchemy import Boolean, CheckConstraint, Enum, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import UserRole, sql_in

PHONE_PATTERN = r"^\+8801[3-9][0-9]{8}$"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone"),
        UniqueConstraint("email"),
        CheckConstraint(f"phone ~ '{PHONE_PATTERN}'", name="phone_format"),
        CheckConstraint(f"role IN ({sql_in(UserRole)})", name="role_valid"),
    )

    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(14))
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    # varchar + CHECK instead of a native Postgres enum (see docs/database_schema.md).
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        server_default=UserRole.CITIZEN.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
