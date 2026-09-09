"""Persist retryable local file deletion intents.

Revision ID: 20260909_0019
Revises: 20260909_0018
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0019"
down_revision = "20260909_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "file_cleanup_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("storage_scope", sa.String(36), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(64), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('file', 'project')", name="kind_allowed"),
        sa.CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
    )
    op.create_index("ix_file_cleanup_jobs_next_attempt_at", "file_cleanup_jobs", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_file_cleanup_jobs_next_attempt_at", table_name="file_cleanup_jobs")
    op.drop_table("file_cleanup_jobs")
