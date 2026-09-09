"""Persist shared authentication and account operation budgets.

Revision ID: 20260909_0017
Revises: 20260816_0016
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0017"
down_revision = "20260816_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "request_budgets",
        sa.Column("scope", sa.String(32), primary_key=True),
        sa.Column("identity_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.CheckConstraint("used > 0", name="used_positive"),
    )
    op.create_index("ix_request_budgets_expires_at", "request_budgets", ["expires_at"])


def downgrade():
    op.drop_index("ix_request_budgets_expires_at", table_name="request_budgets")
    op.drop_table("request_budgets")
