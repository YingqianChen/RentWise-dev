"""Add candidate field facts, evidence, and user revision records.

Revision ID: 20260813_0015
Revises: 20260812_0014
Create Date: 2026-08-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


revision = "20260813_0015"
down_revision = "20260812_0014"
branch_labels = None
depends_on = None


FIELD_KEYS_SQL = (
    "'monthly_rent', 'management_fee_amount', 'management_fee_included', "
    "'rates_amount', 'rates_included', 'deposit', 'agent_fee', 'lease_term', "
    "'move_in_date', 'repair_responsibility', 'district', 'address_text', "
    "'building_name', 'nearest_station'"
)


def upgrade() -> None:
    op.create_table(
        "candidate_field_facts",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("field_key", sa.String(length=50), nullable=False),
        sa.Column(
            "system_value",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("system_state", sa.String(length=50), nullable=False),
        sa.Column("system_confidence", sa.String(length=50), nullable=False),
        sa.Column("user_action", sa.String(length=50), nullable=True),
        sa.Column(
            "user_value",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("user_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"field_key IN ({FIELD_KEYS_SQL})",
            name="field_key_allowed",
        ),
        sa.CheckConstraint(
            "system_state IN ('explicit', 'inferred', 'conflicted', 'unknown')",
            name="system_state_allowed",
        ),
        sa.CheckConstraint(
            "system_confidence IN ('high', 'medium', 'low')",
            name="system_confidence_allowed",
        ),
        sa.CheckConstraint(
            "((system_state IN ('explicit', 'inferred') AND system_value IS NOT NULL) OR "
            "(system_state IN ('conflicted', 'unknown') AND system_value IS NULL))",
            name="system_value_matches_state",
        ),
        sa.CheckConstraint(
            "user_action IS NULL OR user_action IN ('confirmed', 'corrected', 'marked_unknown')",
            name="user_action_allowed",
        ),
        sa.CheckConstraint(
            "((user_action IS NULL AND user_value IS NULL) OR "
            "(user_action IN ('confirmed', 'corrected') AND user_value IS NOT NULL) OR "
            "(user_action = 'marked_unknown' AND user_value IS NULL))",
            name="user_value_matches_action",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate_listings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("candidate_id", "field_key"),
    )

    op.create_table(
        "candidate_field_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("field_key", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_asset_id", sa.UUID(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column(
            "claim_value",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=False,
        ),
        sa.Column("claim_kind", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('listing', 'chat', 'note', 'image_ocr')",
            name="source_type_allowed",
        ),
        sa.CheckConstraint(
            "((source_type = 'image_ocr' AND source_asset_id IS NOT NULL) OR "
            "(source_type != 'image_ocr' AND source_asset_id IS NULL))",
            name="source_asset_matches_type",
        ),
        sa.CheckConstraint(
            "claim_kind IN ('explicit', 'inferred')",
            name="claim_kind_allowed",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="confidence_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "field_key"],
            ["candidate_field_facts.candidate_id", "candidate_field_facts.field_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["candidate_source_assets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_field_evidence_candidate_id",
        "candidate_field_evidence",
        ["candidate_id"],
    )
    op.create_index(
        "ix_candidate_field_evidence_source_asset_id",
        "candidate_field_evidence",
        ["source_asset_id"],
    )

    op.create_table(
        "candidate_field_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("field_key", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "previous_value",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('confirm', 'correct', 'mark_unknown', 'revert')",
            name="action_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "field_key"],
            ["candidate_field_facts.candidate_id", "candidate_field_facts.field_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_field_revisions_candidate_id",
        "candidate_field_revisions",
        ["candidate_id"],
    )
    op.create_index(
        "ix_candidate_field_revisions_actor_user_id",
        "candidate_field_revisions",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_field_revisions_actor_user_id",
        table_name="candidate_field_revisions",
    )
    op.drop_index(
        "ix_candidate_field_revisions_candidate_id",
        table_name="candidate_field_revisions",
    )
    op.drop_table("candidate_field_revisions")
    op.drop_index(
        "ix_candidate_field_evidence_source_asset_id",
        table_name="candidate_field_evidence",
    )
    op.drop_index(
        "ix_candidate_field_evidence_candidate_id",
        table_name="candidate_field_evidence",
    )
    op.drop_table("candidate_field_evidence")
    op.drop_table("candidate_field_facts")
