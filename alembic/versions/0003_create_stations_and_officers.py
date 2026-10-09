"""create stations and officers; add users.station_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(5), nullable=False),
        sa.Column("city", sa.String(60), nullable=False),
        sa.Column("city_code", sa.String(3), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stations")),
        sa.UniqueConstraint("code", name=op.f("uq_stations_code")),
        sa.UniqueConstraint("city", "name", name=op.f("uq_stations_city_name")),
        sa.CheckConstraint("code ~ '^[A-Z]{2,5}$'", name=op.f("ck_stations_code_format")),
        sa.CheckConstraint("city_code ~ '^[A-Z]{3}$'", name=op.f("ck_stations_city_code_format")),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name=op.f("ck_stations_lat_range")),
        sa.CheckConstraint("lng BETWEEN -180 AND 180", name=op.f("ck_stations_lng_range")),
    )

    op.add_column("users", sa.Column("station_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_station_id_stations"),
        "users",
        "stations",
        ["station_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_users_station_id"), "users", ["station_id"])
    op.create_check_constraint(
        op.f("ck_users_station_admin_station"),
        "users",
        "(role = 'station_admin') = (station_id IS NOT NULL)",
    )

    op.create_table(
        "officers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("station_id", sa.BigInteger(), nullable=False),
        sa.Column("badge_no", sa.String(20), nullable=False),
        sa.Column("rank", sa.String(40), nullable=False),
        sa.Column("duty_status", sa.String(10), server_default="off_duty", nullable=False),
        sa.Column("last_lat", sa.Float(), nullable=True),
        sa.Column("last_lng", sa.Float(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_officers")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_officers_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_officers_station_id_stations"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_officers_user_id")),
        sa.UniqueConstraint("badge_no", name=op.f("uq_officers_badge_no")),
        sa.CheckConstraint(
            "duty_status IN ('off_duty', 'available', 'busy')",
            name=op.f("ck_officers_duty_status_valid"),
        ),
        sa.CheckConstraint(
            "(last_lat IS NULL) = (last_lng IS NULL)", name=op.f("ck_officers_location_pair")
        ),
        sa.CheckConstraint("last_lat BETWEEN -90 AND 90", name=op.f("ck_officers_lat_range")),
        sa.CheckConstraint("last_lng BETWEEN -180 AND 180", name=op.f("ck_officers_lng_range")),
    )
    op.create_index("ix_officers_station_id_duty_status", "officers", ["station_id", "duty_status"])
    op.create_index(
        "ix_officers_available_last_seen_at",
        "officers",
        ["last_seen_at"],
        postgresql_where=sa.text("duty_status = 'available'"),
    )


def downgrade() -> None:
    op.drop_table("officers")
    op.drop_constraint(op.f("ck_users_station_admin_station"), "users", type_="check")
    op.drop_index(op.f("ix_users_station_id"), table_name="users")
    op.drop_constraint(op.f("fk_users_station_id_stations"), "users", type_="foreignkey")
    op.drop_column("users", "station_id")
    op.drop_table("stations")
