"""Dual peak-window default: paired_payload column + peak_both default.

Revision ID: 20260507_0011
Revises: 20260507_0010
Create Date: 2026-05-07 13:00:00.000000

Adds:
- ``candidate_commute_evidence.paired_payload`` JSONB column for the EVENING
  half of the evidence when a project's commute window is ``peak_both``.
- Switches the ``search_projects.commute_departure_window`` server_default
  from ``"now"`` to ``"peak_both"``. Existing rows keep their explicitly-set
  values; only newly inserted rows pick up the new default.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0011"
down_revision = "20260507_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_commute_evidence",
        sa.Column(
            "paired_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.alter_column(
        "search_projects",
        "commute_departure_window",
        server_default="peak_both",
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "search_projects",
        "commute_departure_window",
        server_default="now",
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )
    op.drop_column("candidate_commute_evidence", "paired_payload")
