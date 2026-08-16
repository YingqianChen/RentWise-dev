from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateFieldEvidence
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
        self.assertEqual(result["groups"].best_current_option.decision_confidence, "high")
        self.assertEqual(len(result["groups"].viable_alternatives), 1)
        self.assertEqual(result["groups"].viable_alternatives[0].name, "Still Viable")
        self.assertEqual(len(result["groups"].not_ready_for_fair_comparison), 1)
        self.assertEqual(result["groups"].not_ready_for_fair_comparison[0].name, "Needs Cost Check")
        self.assertEqual(result["groups"].not_ready_for_fair_comparison[0].decision_confidence, "low")
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

    def test_compare_surfaces_evidence_coverage_and_source_types(self):
        project = build_project(build_user())
        candidate = build_candidate(project, name="Evidence Summary")
        facts = {fact.field_key: fact for fact in candidate.field_facts}
        facts["management_fee_amount"].system_state = "inferred"
        facts["management_fee_amount"].system_value = 800
        facts["rates_amount"].system_state = "conflicted"
        facts["rates_amount"].system_value = None
        facts["monthly_rent"].user_action = "confirmed"
        facts["monthly_rent"].evidence = [
            CandidateFieldEvidence(
                id=uuid.uuid4(),
                candidate_id=candidate.id,
                field_key="monthly_rent",
                source_type="listing",
                source_asset_id=None,
                quote="Rent 18000",
                claim_value=18000,
                claim_kind="explicit",
                confidence="high",
            )
        ]

        result = ComparisonService().compare(project, [candidate, build_candidate(project, name="Peer")])
        summary = next(
            card.evidence_summary
            for card in [
                result["groups"].best_current_option,
                *result["groups"].viable_alternatives,
                *result["groups"].not_ready_for_fair_comparison,
                *result["groups"].likely_drop,
            ]
            if card and card.name == "Evidence Summary"
        )

        self.assertEqual(summary.explicit_count, 5)
        self.assertEqual(summary.inferred_count, 1)
        self.assertEqual(summary.conflicted_count, 1)
        self.assertEqual(summary.unresolved_count, 7)
        self.assertEqual(summary.source_labels, ["Listing text", "User update"])

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

    def test_user_rejection_is_explicit_and_does_not_change_system_recommendation(self):
        project = build_project(build_user())
        user_rejected = build_candidate(
            project,
            name="User Rejected",
            status="follow_up",
            user_decision="rejected",
            next_best_action="schedule_viewing",
        )
        user_rejected.candidate_assessment.status = "follow_up"
        user_rejected.candidate_assessment.recommendation_confidence = "high"
        comparison_peer = build_candidate(project, name="Peer")

        result = ComparisonService().compare(project, [user_rejected, comparison_peer])
        card = result["groups"].likely_drop[0]

        self.assertEqual(card.user_decision, "rejected")
        self.assertEqual(card.top_recommendation, "shortlist_recommendation")
        self.assertIn("rejected by you", card.decision_explanation.lower())
        self.assertIn("system", card.decision_explanation.lower())

    def test_system_reject_remains_explicit_when_user_shortlists_candidate(self):
        project = build_project(build_user())
        user_shortlisted = build_candidate(
            project,
            name="Contradictory Choice",
            status="recommended_reject",
            user_decision="shortlisted",
            next_best_action="reject",
        )
        user_shortlisted.candidate_assessment.status = "recommended_reject"
        comparison_peer = build_candidate(project, name="Peer")

        result = ComparisonService().compare(project, [user_shortlisted, comparison_peer])
        card = result["groups"].likely_drop[0]

        self.assertEqual(card.user_decision, "shortlisted")
        self.assertEqual(card.top_recommendation, "likely_reject")
        self.assertIn("shortlisted by you", card.decision_explanation.lower())
        self.assertIn("system", card.decision_explanation.lower())

    def test_unmodeled_furnishing_does_not_change_comparison_fit(self):
        project = build_project(build_user())
        furnished = build_candidate(project, name="Furnished")
        unfurnished = build_candidate(project, name="Unfurnished")
        furnished.extracted_info.furnished = "furnished"
        unfurnished.extracted_info.furnished = "unfurnished"

        service = ComparisonService()

        self.assertEqual(
            service._project_fit_score(project, furnished),
            service._project_fit_score(project, unfurnished),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
