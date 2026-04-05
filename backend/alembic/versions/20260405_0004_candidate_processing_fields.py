"""Add candidate processing fields for background imports.

Revision ID: 20260405_0004
Revises: 20260405_0003
Create Date: 2026-04-05 21:25:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260405_0004"
down_revision = "20260405_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_listings",
        sa.Column("processing_stage", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "candidate_listings",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_listings", "processing_error")
    op.drop_column("candidate_listings", "processing_stage")
