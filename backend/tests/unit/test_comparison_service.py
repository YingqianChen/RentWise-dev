from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.comparison_service import ComparisonService
from tests.helpers import build_candidate, build_project, build_user


class ComparisonServiceTests(TestCase):
    def test_compare_groups_candidates_and_explains_why(self):
        user = build_user()
        project = build_project(user)

        lead = build_candidate(project, name="Stable Lead", status="follow_up", next_best_action="schedule_viewing")
        lead.cost_assessment.monthly_cost_confidence = "high"
        lead.cost_assessment.cost_risk_flag = "none"
        lead.clause_assessment.clause_risk_flag = "none"
        lead.candidate_assessment.recommendation_confidence = "high"
        lead.candidate_assessment.critical_uncertainty_level = "low"

        viable = build_candidate(project, name="Still Viable", status="follow_up", next_best_action="keep_warm")
        viable.cost_assessment.monthly_cost_confidence = "medium"
        viable.cost_assessment.cost_risk_flag = "none"
        viable.candidate_assessment.recommendation_confidence = "medium"
        viable.candidate_assessment.critical_uncertainty_level = "medium"

        not_ready = build_candidate(project, name="Needs Cost Check", status="needs_info", next_best_action="verify_cost")
        not_ready.candidate_assessment.recommendation_confidence = "low"
        not_ready.candidate_assessment.critical_uncertainty_level = "high"
        not_ready.cost_assessment.monthly_cost_missing_items = [
            "management_fee_amount",
            "rates_amount",
        ]

        drop = build_candidate(project, name="Weak Option", status="recommended_reject", next_best_action="reject")

        result = ComparisonService().compare(project, [lead, viable, not_ready, drop])

        self.assertEqual(result["groups"].best_current_option.name, "Stable Lead")
        self.assertEqual(len(result["groups"].viable_alternatives), 1)
        self.assertEqual(result["groups"].viable_alternatives[0].name, "Still Viable")
        self.assertEqual(len(result["groups"].not_ready_for_fair_comparison), 1)
        self.assertEqual(result["groups"].not_ready_for_fair_comparison[0].name, "Needs Cost Check")
        self.assertEqual(len(result["groups"].likely_drop), 1)
        self.assertEqual(result["groups"].likely_drop[0].name, "Weak Option")
        self.assertIsNone(result["groups"].best_current_option.benchmark)
        self.assertIn("strongest current option", result["summary"].headline.lower())
        self.assertTrue(result["recommended_next_actions"].questions_to_ask)
        self.assertIsNotNone(result["recommended_next_actions"].contact_first)

    def test_not_ready_candidate_surfaces_specific_blocker(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project, name="Fee Unknown", next_best_action="verify_cost")
        candidate.cost_assessment.monthly_cost_missing_items = ["management_fee_amount"]
        candidate.candidate_assessment.recommendation_confidence = "low"
        candidate.candidate_assessment.critical_uncertainty_level = "high"

        result = ComparisonService().compare(project, [candidate, build_candidate(project, name="Lead", status="follow_up", next_best_action="schedule_viewing")])
        card = result["groups"].not_ready_for_fair_comparison[0]

        self.assertIn("management fee", (card.open_blocker or "").lower())
        self.assertIn("cannot be compared fairly", card.decision_explanation.lower())

    def test_compare_uses_softer_repair_blocker_for_supported_signal(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project, name="Repair Support", next_best_action="verify_clause")
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.monthly_cost_missing_items = []
        candidate.cost_assessment.cost_risk_flag = "none"
        candidate.clause_assessment.repair_responsibility_level = "supported_but_unconfirmed"
        candidate.clause_assessment.clause_risk_flag = "needs_confirmation"
        candidate.candidate_assessment.recommendation_confidence = "low"
        candidate.candidate_assessment.critical_uncertainty_level = "high"

        lead = build_candidate(project, name="Lead", status="follow_up", next_best_action="schedule_viewing")
        lead.cost_assessment.monthly_cost_confidence = "high"
        lead.cost_assessment.cost_risk_flag = "none"
        lead.clause_assessment.clause_risk_flag = "none"
        lead.candidate_assessment.recommendation_confidence = "high"

        result = ComparisonService().compare(project, [candidate, lead])
        card = result["groups"].not_ready_for_fair_comparison[0]

        self.assertIn("promising", (card.open_blocker or "").lower())

    def test_compare_preview_surfaces_suggested_workspace(self):
        user = build_user()
        project = build_project(user)

        lead = build_candidate(project, name="Lead", status="follow_up", next_best_action="schedule_viewing")
        lead.cost_assessment.monthly_cost_confidence = "high"
        lead.cost_assessment.cost_risk_flag = "none"
        lead.clause_assessment.clause_risk_flag = "none"
        lead.candidate_assessment.recommendation_confidence = "high"

        support = build_candidate(project, name="Support", status="follow_up", next_best_action="keep_warm")
        support.candidate_assessment.recommendation_confidence = "medium"

        preview = ComparisonService().build_compare_preview(project, [lead, support])

        self.assertIsNotNone(preview)
        self.assertEqual(len(preview.candidate_ids), 2)
        self.assertIn("strongest current option", preview.headline.lower())

    def test_compare_suggestions_exclude_non_completed_candidates_with_stale_results(self):
        project = build_project(build_user())
        completed = build_candidate(project, name="Usable")
        failed = build_candidate(project, name="Stale")
        failed.processing_stage = "failed"

        suggested = ComparisonService().suggest_compare_ids([completed, failed])

        self.assertEqual(suggested, [completed.id])


if __name__ == "__main__":
    import unittest

    unittest.main()
