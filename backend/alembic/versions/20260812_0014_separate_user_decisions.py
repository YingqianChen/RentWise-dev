"""Separate user decisions from system assessment statuses.

Revision ID: 20260812_0014
Revises: 20260812_0013
Create Date: 2026-08-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260812_0014"
down_revision = "20260812_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE candidate_assessments
        SET status = CASE
            WHEN next_best_action = 'reject' THEN 'recommended_reject'
            WHEN next_best_action IN ('verify_cost', 'verify_clause')
                 AND decision_risk_level = 'high' THEN 'high_risk_pending'
            WHEN next_best_action IN ('verify_cost', 'verify_clause')
                 OR critical_uncertainty_level IN ('high', 'medium') THEN 'needs_info'
            ELSE 'follow_up'
        END
        """
    )
    op.execute(
        """
        UPDATE candidate_listings AS candidate
        SET status = assessment.status
        FROM candidate_assessments AS assessment
        WHERE assessment.candidate_id = candidate.id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE candidate_assessments AS assessment
        SET status = CASE
            WHEN candidate.user_decision = 'shortlisted' THEN 'shortlisted'
            WHEN candidate.user_decision = 'rejected' THEN 'recommended_reject'
            ELSE assessment.status
        END
        FROM candidate_listings AS candidate
        WHERE candidate.id = assessment.candidate_id
        """
    )
    op.execute(
        """
        UPDATE candidate_listings AS candidate
        SET status = CASE
            WHEN candidate.user_decision = 'shortlisted' THEN 'shortlisted'
            WHEN candidate.user_decision = 'rejected' THEN 'recommended_reject'
            ELSE assessment.status
        END
        FROM candidate_assessments AS assessment
        WHERE assessment.candidate_id = candidate.id
        """
    )
