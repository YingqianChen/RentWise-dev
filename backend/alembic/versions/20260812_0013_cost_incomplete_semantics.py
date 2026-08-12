"""Rename ambiguous hidden-cost state to incomplete.

Revision ID: 20260812_0013
Revises: 20260811_0012
Create Date: 2026-08-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260812_0013"
down_revision = "20260811_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE candidate_cost_assessments
        SET cost_risk_flag = 'incomplete'
        WHERE cost_risk_flag = 'hidden_cost_risk'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE candidate_cost_assessments
        SET cost_risk_flag = 'hidden_cost_risk'
        WHERE cost_risk_flag = 'incomplete'
        """
    )
