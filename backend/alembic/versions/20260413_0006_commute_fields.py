"""Add commute configuration to projects and location evidence to candidates.

Revision ID: 20260413_0006
Revises: 20260406_0005
Create Date: 2026-04-13 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260413_0006"
down_revision = "20260406_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- SearchProject commute fields --
    op.add_column(
        "search_projects",
        sa.Column("commute_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "search_projects",
        sa.Column("commute_destination_label", sa.String(255), nullable=True),
    )
    op.add_column(
        "search_projects",
        sa.Column("commute_destination_query", sa.String(500), nullable=True),
    )
    op.add_column(
        "search_projects",
        sa.Column("commute_mode", sa.String(50), nullable=True),
    )
    op.add_column(
        "search_projects",
        sa.Column("max_commute_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_projects",
        sa.Column("commute_destination_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "search_projects",
        sa.Column("commute_destination_lng", sa.Float(), nullable=True),
    )

    # -- CandidateExtractedInfo location evidence fields --
    op.add_column(
        "candidate_extracted_info",
        sa.Column("address_text", sa.String(500), nullable=True),
    )
    op.add_column(
        "candidate_extracted_info",
        sa.Column("building_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "candidate_extracted_info",
        sa.Column("nearest_station", sa.String(255), nullable=True),
    )
    op.add_column(
        "candidate_extracted_info",
        sa.Column(
            "location_confidence",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column(
        "candidate_extracted_info",
        sa.Column(
            "location_source",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )


def downgrade() -> None:
    # -- CandidateExtractedInfo --
    op.drop_column("candidate_extracted_info", "location_source")
    op.drop_column("candidate_extracted_info", "location_confidence")
    op.drop_column("candidate_extracted_info", "nearest_station")
    op.drop_column("candidate_extracted_info", "building_name")
    op.drop_column("candidate_extracted_info", "address_text")

    # -- SearchProject --
    op.drop_column("search_projects", "commute_destination_lng")
    op.drop_column("search_projects", "commute_destination_lat")
    op.drop_column("search_projects", "max_commute_minutes")
    op.drop_column("search_projects", "commute_mode")
    op.drop_column("search_projects", "commute_destination_query")
    op.drop_column("search_projects", "commute_destination_label")
    op.drop_column("search_projects", "commute_enabled")
