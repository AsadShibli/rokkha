from sqlalchemy import CheckConstraint, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

STATION_CODE_PATTERN = r"^[A-Z]{2,5}$"
CITY_CODE_PATTERN = r"^[A-Z]{3}$"


class Station(IdMixin, TimestampMixin, Base):
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("city", "name"),
        CheckConstraint(f"code ~ '{STATION_CODE_PATTERN}'", name="code_format"),
        CheckConstraint(f"city_code ~ '{CITY_CODE_PATTERN}'", name="city_code_format"),
        CheckConstraint("lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="lng_range"),
    )

    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(5))
    city: Mapped[str] = mapped_column(String(60))
    city_code: Mapped[str] = mapped_column(String(3))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
