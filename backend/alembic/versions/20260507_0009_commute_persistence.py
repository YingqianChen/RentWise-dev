"""Persist commute evidence and add departure-window config.

Revision ID: 20260507_0009
Revises: 20260418_0008
Create Date: 2026-05-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0009"
down_revision = "20260418_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Project-level departure config
    op.add_column(
        "search_projects",
        sa.Column(
            "commute_departure_window",
            sa.String(length=50),
            server_default="now",
            nullable=False,
        ),
    )
    op.add_column(
        "search_projects",
        sa.Column(
            "commute_departure_time",
            sa.String(length=5),
            nullable=True,
        ),
    )

    # 2. Candidate-level commute evidence cache (mirrors CommuteEvidence schema)
    op.create_table(
        "candidate_commute_evidence",
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidate_listings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("config_signature", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=50), nullable=True),
        sa.Column("route_summary", sa.Text(), nullable=True),
        sa.Column("origin_station", sa.String(length=255), nullable=True),
        sa.Column("destination_station", sa.String(length=255), nullable=True),
        sa.Column(
            "segments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("destination_label", sa.String(length=255), nullable=True),
        sa.Column("confidence_note", sa.Text(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("candidate_commute_evidence")
    op.drop_column("search_projects", "commute_departure_time")
    op.drop_column("search_projects", "commute_departure_window")
