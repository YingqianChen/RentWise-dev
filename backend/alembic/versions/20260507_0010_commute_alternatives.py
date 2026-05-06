"""Add alternatives column to commute evidence cache.

Revision ID: 20260507_0010
Revises: 20260507_0009
Create Date: 2026-05-07 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0010"
down_revision = "20260507_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_commute_evidence",
        sa.Column(
            "alternatives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_commute_evidence", "alternatives")
