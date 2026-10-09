"""create gds and gd_sequences

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gds",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("gd_number", sa.String(30), nullable=False),
        sa.Column("citizen_id", sa.BigInteger(), nullable=False),
        sa.Column("station_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(15), server_default="submitted", nullable=False),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gds")),
        sa.ForeignKeyConstraint(
            ["citizen_id"], ["users.id"], name=op.f("fk_gds_citizen_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_gds_station_id_stations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_gds_reviewed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("gd_number", name=op.f("uq_gds_gd_number")),
        sa.CheckConstraint(
            "category IN ('lost_item', 'lost_document', 'missing_person', 'threat', "
            "'harassment', 'other')",
            name=op.f("ck_gds_category_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', 'rejected')",
            name=op.f("ck_gds_status_valid"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('approved', 'rejected') "
            "OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name=op.f("ck_gds_final_is_reviewed"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR review_note IS NOT NULL", name=op.f("ck_gds_reject_has_note")
        ),
    )
    op.create_index("ix_gds_citizen_id_created_at", "gds", ["citizen_id", "created_at"])
    op.create_index(
        "ix_gds_station_id_status_created_at", "gds", ["station_id", "status", "created_at"]
    )

    op.create_table(
        "gd_sequences",
        sa.Column("station_id", sa.BigInteger(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("last_value", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("station_id", "year", name=op.f("pk_gd_sequences")),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_gd_sequences_station_id_stations"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("last_value >= 0", name=op.f("ck_gd_sequences_last_value_non_negative")),
    )


def downgrade() -> None:
    op.drop_table("gd_sequences")
    op.drop_table("gds")
