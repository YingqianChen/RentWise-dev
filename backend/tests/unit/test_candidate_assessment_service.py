from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_assessment_service import CandidateAssessmentService
from tests.helpers import build_candidate, build_project, build_user


class CandidateAssessmentServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = CandidateAssessmentService()
        self.user = build_user()
        self.project = build_project(self.user)

    def test_trust_signal_raises_decision_risk_and_verify_clause_action(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.decision_signals = [
            {
                "key": "holding_fee_risk",
                "category": "trust",
                "label": "Holding money refund is unclear",
                "source": "chat",
                "evidence": "If u don't like after viewing I give back (maybe).",
                "note": "Needs written confirmation.",
            }
        ]
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.known_monthly_cost = 18000
        candidate.cost_assessment.cost_risk_flag = "none"
        candidate.clause_assessment.clause_confidence = "high"
        candidate.clause_assessment.clause_risk_flag = "none"

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=self.project.max_budget,
            preferred_districts=self.project.preferred_districts,
            must_have=self.project.must_have,
            deal_breakers=self.project.deal_breakers,
            move_in_target=self.project.move_in_target,
        )

        self.assertEqual(assessment.decision_risk_level, "high")
        self.assertEqual(assessment.next_best_action, "verify_clause")
        self.assertIn("Trust concern", assessment.labels)

    def test_shared_bathroom_signal_can_trigger_hard_conflict(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.decision_signals = [
            {
                "key": "bathroom_sharing",
                "category": "living_arrangement",
                "label": "Shared bathroom with one other tenant",
                "source": "chat",
                "evidence": "Share with one person only.",
                "note": "",
            }
        ]

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=self.project.max_budget,
            preferred_districts=self.project.preferred_districts,
            must_have=self.project.must_have,
            deal_breakers=self.project.deal_breakers,
            move_in_target=self.project.move_in_target,
            source_text="Agent confirms: Share with one person only.",
        )

        self.assertEqual(assessment.next_best_action, "reject")
        self.assertIn("Hard conflict", assessment.labels)

    def test_unverifiable_shared_bathroom_signal_does_not_trigger_reject(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.decision_signals = [
            {
                "key": "bathroom_sharing",
                "category": "living_arrangement",
                "label": "Shared bathroom",
                "source": "chat",
                "evidence": "Share with one person only.",
                "note": "",
            }
        ]

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=self.project.max_budget,
            deal_breakers=self.project.deal_breakers,
            source_text="The supplied listing does not mention bathroom sharing.",
        )

        self.assertNotEqual(assessment.next_best_action, "reject")
        self.assertNotIn("Hard conflict", assessment.labels)

    def test_all_unknown_information_is_not_low_value_or_high_risk(self):
        candidate = build_candidate(self.project)
        info = candidate.extracted_info
        for field in (
            "monthly_rent",
            "management_fee_amount",
            "rates_amount",
            "deposit",
            "agent_fee",
            "lease_term",
            "move_in_date",
            "repair_responsibility",
            "district",
            "furnished",
            "size_sqft",
            "bedrooms",
        ):
            setattr(info, field, "unknown")
        info.management_fee_included = None
        info.rates_included = None
        info.decision_signals = []
        candidate.cost_assessment.known_monthly_cost = None
        candidate.cost_assessment.monthly_cost_confidence = "low"
        candidate.cost_assessment.cost_risk_flag = "incomplete"
        candidate.clause_assessment.repair_responsibility_level = "unknown"
        candidate.clause_assessment.lease_term_level = "unknown"
        candidate.clause_assessment.move_in_date_level = "unknown"
        candidate.clause_assessment.clause_confidence = "low"
        candidate.clause_assessment.clause_risk_flag = "needs_confirmation"

        assessment = self.service.assess(
            extracted_info=info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=self.project.max_budget,
            must_have=self.project.must_have,
            deal_breakers=self.project.deal_breakers,
            source_text="No useful rental facts were supplied.",
        )

        self.assertEqual(assessment.potential_value_level, "unknown")
        self.assertEqual(assessment.decision_risk_level, "unknown")
        self.assertEqual(assessment.next_best_action, "verify_cost")
        self.assertNotEqual(assessment.status, "recommended_reject")

    def test_unknown_furnishing_does_not_conflict_with_furnished_requirement(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.furnished = "unknown"

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=self.project.max_budget,
            must_have=["furnished"],
            source_text="The listing does not mention furniture.",
        )

        self.assertNotEqual(assessment.next_best_action, "reject")

    def test_source_backed_over_budget_rent_can_trigger_reject(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.monthly_rent = "HKD 30,000"
        candidate.extracted_info.management_fee_included = True
        candidate.extracted_info.rates_included = True
        candidate.cost_assessment.known_monthly_cost = 30000
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.cost_risk_flag = "over_budget"

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=22000,
            source_text="Monthly rent: HKD 30,000, including management fee and rates.",
        )

        self.assertEqual(assessment.next_best_action, "reject")

    def test_unverifiable_over_budget_value_requires_confirmation(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.monthly_rent = "HKD 30,000"
        candidate.cost_assessment.known_monthly_cost = 30000
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.cost_risk_flag = "over_budget"

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=22000,
            source_text="The source says rent is negotiable but gives no number.",
        )

        self.assertNotEqual(assessment.next_best_action, "reject")
        self.assertNotEqual(assessment.status, "recommended_reject")

    def test_low_numeric_rent_does_not_create_market_price_label(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.monthly_rent = "5900"
        candidate.cost_assessment.known_monthly_cost = 5900
        candidate.cost_assessment.cost_risk_flag = "none"

        assessment = self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            max_budget=22000,
            source_text="Rent HKD 5,900.",
        )

        self.assertNotIn("Low price", assessment.labels)
