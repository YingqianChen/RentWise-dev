"""Allow individual access sessions to be revoked on logout.

Revision ID: 20260909_0020
Revises: 20260909_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_0020"
down_revision = "20260909_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_access_tokens",
        sa.Column("revocation_key", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_access_tokens_expires_at", "revoked_access_tokens", ["expires_at"])


def downgrade():
    op.drop_index("ix_revoked_access_tokens_expires_at", table_name="revoked_access_tokens")
    op.drop_table("revoked_access_tokens")
