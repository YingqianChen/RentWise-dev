"""Add raw_facts bucket to candidate extracted info.

Revision ID: 20260418_0007
Revises: 20260413_0006
Create Date: 2026-04-18 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_0007"
down_revision = "20260413_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_extracted_info",
        sa.Column(
            "raw_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_extracted_info", "raw_facts")
