"""Add stable candidate processing error code.

Revision ID: 20260811_0012
Revises: 20260507_0011
Create Date: 2026-08-11 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260811_0012"
down_revision = "20260507_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_listings",
        sa.Column("processing_error_code", sa.String(length=50), nullable=True),
    )
    op.execute(
        """
        UPDATE candidate_listings
        SET processing_error_code = 'legacy_unknown'
        WHERE processing_stage = 'failed'
          AND processing_error_code IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("candidate_listings", "processing_error_code")
