"""Freeze fee billing units in user facts and their revision history.

Revision ID: 20260909_0018
Revises: 20260909_0017
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0018"
down_revision = "20260909_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_field_facts", sa.Column("user_billing_period", sa.String(16), nullable=True))
    op.create_check_constraint(
        "billing_period_allowed",
        "candidate_field_facts",
        "user_billing_period IS NULL OR user_billing_period IN ('month', 'quarter', 'year', 'unknown')",
    )
    op.add_column("candidate_field_revisions", sa.Column("previous_billing_period", sa.String(16), nullable=True))
    op.add_column("candidate_field_revisions", sa.Column("new_billing_period", sa.String(16), nullable=True))


def downgrade():
    op.drop_column("candidate_field_revisions", "new_billing_period")
    op.drop_column("candidate_field_revisions", "previous_billing_period")
    op.drop_constraint(op.f("ck_candidate_field_facts_billing_period_allowed"), "candidate_field_facts", type_="check")
    op.drop_column("candidate_field_facts", "user_billing_period")
