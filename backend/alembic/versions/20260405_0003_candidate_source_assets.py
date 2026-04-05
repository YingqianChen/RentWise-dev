"""add candidate source assets

Revision ID: 20260405_0003
Revises: 20260405_0002
Create Date: 2026-04-05 19:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260405_0003"
down_revision = "20260405_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_source_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("ocr_status", sa.String(length=50), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_source_assets_candidate_id",
        "candidate_source_assets",
        ["candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_source_assets_candidate_id", table_name="candidate_source_assets")
    op.drop_table("candidate_source_assets")
