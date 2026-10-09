"""create incidents and incident_events

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = "'pending', 'assigned', 'en_route', 'resolved', 'cancelled'"


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
        "incidents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("citizen_id", sa.BigInteger(), nullable=False),
        sa.Column("officer_id", sa.BigInteger(), nullable=True),
        sa.Column("station_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.ForeignKeyConstraint(
            ["citizen_id"],
            ["users.id"],
            name=op.f("fk_incidents_citizen_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["officer_id"],
            ["officers.id"],
            name=op.f("fk_incidents_officer_id_officers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_incidents_station_id_stations"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("type IN ('sos', 'report')", name=op.f("ck_incidents_type_valid")),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_incidents_status_valid")),
        sa.CheckConstraint(
            "status = 'cancelled' OR (status = 'pending') = (officer_id IS NULL)",
            name=op.f("ck_incidents_officer_matches_status"),
        ),
        sa.CheckConstraint(
            "status <> 'resolved' OR resolved_at IS NOT NULL",
            name=op.f("ck_incidents_resolved_at_set"),
        ),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name=op.f("ck_incidents_cancelled_at_set"),
        ),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name=op.f("ck_incidents_lat_range")),
        sa.CheckConstraint("lng BETWEEN -180 AND 180", name=op.f("ck_incidents_lng_range")),
    )
    op.create_index(
        "uq_incidents_open_sos_per_citizen",
        "incidents",
        ["citizen_id"],
        unique=True,
        postgresql_where=sa.text("type = 'sos' AND status IN ('pending', 'assigned', 'en_route')"),
    )
    op.create_index(
        "uq_incidents_active_per_officer",
        "incidents",
        ["officer_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('assigned', 'en_route')"),
    )
    op.create_index("ix_incidents_citizen_id_created_at", "incidents", ["citizen_id", "created_at"])
    op.create_index("ix_incidents_officer_id_created_at", "incidents", ["officer_id", "created_at"])
    op.create_index(
        "ix_incidents_station_id_status_created_at",
        "incidents",
        ["station_id", "status", "created_at"],
    )

    op.create_table(
        "incident_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("incident_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("officer_id", sa.BigInteger(), nullable=True),
        sa.Column("from_status", sa.String(12), nullable=True),
        sa.Column("to_status", sa.String(12), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_events")),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_events_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_incident_events_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["officer_id"],
            ["officers.id"],
            name=op.f("fk_incident_events_officer_id_officers"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"to_status IN ({STATUSES})", name=op.f("ck_incident_events_to_status_valid")
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({STATUSES})",
            name=op.f("ck_incident_events_from_status_valid"),
        ),
    )
    op.create_index(
        "ix_incident_events_incident_id_created_at",
        "incident_events",
        ["incident_id", "created_at"],
    )
    op.create_index(op.f("ix_incident_events_officer_id"), "incident_events", ["officer_id"])


def downgrade() -> None:
    op.drop_table("incident_events")
    op.drop_table("incidents")
