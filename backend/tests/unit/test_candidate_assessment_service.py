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
        self.project = build_project(build_user())

    def _assess(self, candidate):
        return self.service.assess(
            extracted_info=candidate.extracted_info,
            cost_assessment=candidate.cost_assessment,
            clause_assessment=candidate.clause_assessment,
            preferred_districts=self.project.preferred_districts,
        )

    def test_unmodeled_decision_signals_do_not_change_recommendation(self):
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
        candidate.clause_assessment.repair_responsibility_level = "clear"

        with_signal = self._assess(candidate)
        candidate.extracted_info.decision_signals = []
        without_signal = self._assess(candidate)

        self.assertEqual(with_signal.next_best_action, without_signal.next_best_action)
        self.assertEqual(with_signal.decision_risk_level, without_signal.decision_risk_level)
        self.assertNotIn("Trust concern", with_signal.labels)

    def test_shared_bathroom_signal_cannot_trigger_reject(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.bedrooms = "Room with shared bathroom"
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

        assessment = self._assess(candidate)

        self.assertNotEqual(assessment.next_best_action, "reject")
        self.assertNotIn("Hard conflict", assessment.labels)

    def test_furnishing_cannot_change_candidate_value_or_reject(self):
        candidate = build_candidate(self.project)
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.cost_risk_flag = "none"
        candidate.clause_assessment.clause_confidence = "high"
        candidate.clause_assessment.clause_risk_flag = "none"

        candidate.extracted_info.furnished = "furnished"
        furnished = self._assess(candidate)
        candidate.extracted_info.furnished = "unfurnished"
        unfurnished = self._assess(candidate)

        self.assertEqual(furnished.potential_value_level, unfurnished.potential_value_level)
        self.assertEqual(furnished.next_best_action, unfurnished.next_best_action)

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
        ):
            setattr(info, field, None)
        info.management_fee_included = None
        info.rates_included = None
        candidate.cost_assessment.known_monthly_cost = None
        candidate.cost_assessment.monthly_cost_confidence = "low"
        candidate.cost_assessment.cost_risk_flag = "incomplete"
        candidate.clause_assessment.repair_responsibility_level = "unknown"
        candidate.clause_assessment.lease_term_level = "unknown"
        candidate.clause_assessment.move_in_date_level = "unknown"
        candidate.clause_assessment.clause_confidence = "low"
        candidate.clause_assessment.clause_risk_flag = "needs_confirmation"

        assessment = self._assess(candidate)

        self.assertEqual(assessment.potential_value_level, "unknown")
        self.assertEqual(assessment.decision_risk_level, "unknown")
        self.assertEqual(assessment.next_best_action, "verify_cost")
        self.assertNotEqual(assessment.status, "recommended_reject")

    def test_trusted_over_budget_cost_triggers_reject(self):
        candidate = build_candidate(self.project)
        candidate.cost_assessment.known_monthly_cost = 30000
        candidate.cost_assessment.monthly_cost_confidence = "high"
        candidate.cost_assessment.cost_risk_flag = "over_budget"

        assessment = self._assess(candidate)

        self.assertEqual(assessment.next_best_action, "reject")
        self.assertEqual(assessment.status, "recommended_reject")

    def test_low_numeric_rent_does_not_create_market_price_label(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.monthly_rent = "5900"
        candidate.cost_assessment.known_monthly_cost = 5900
        candidate.cost_assessment.cost_risk_flag = "none"

        assessment = self._assess(candidate)

        self.assertNotIn("Low price", assessment.labels)
