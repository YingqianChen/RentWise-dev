"""Add legal_references bucket to clause assessment.

Revision ID: 20260418_0008
Revises: 20260418_0007
Create Date: 2026-04-18 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_0008"
down_revision = "20260418_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_clause_assessments",
        sa.Column(
            "legal_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_clause_assessments", "legal_references")
