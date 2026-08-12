from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.cost_assessment_service import CostAssessmentService
from tests.helpers import build_candidate, build_project, build_user


class CostAssessmentServiceTests(TestCase):
    def setUp(self) -> None:
        self.candidate = build_candidate(build_project(build_user()))
        self.service = CostAssessmentService()

    def test_unspecified_fee_inclusion_is_incomplete_not_risk(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "18000"
        info.management_fee_amount = "unknown"
        info.management_fee_included = None
        info.rates_amount = "unknown"
        info.rates_included = None

        result = self.service.assess(info, max_budget=22000)

        self.assertEqual(result.known_monthly_cost, 18000)
        self.assertEqual(result.cost_risk_flag, "incomplete")
        self.assertNotIn("risk", result.summary.lower())

    def test_explicit_separate_fee_without_amount_is_possible_additional_cost(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "18000"
        info.management_fee_amount = "unknown"
        info.management_fee_included = False
        info.rates_included = True
        info.deposit = "2 months"
        info.agent_fee = "half month"

        result = self.service.assess(info, max_budget=22000)

        self.assertEqual(result.cost_risk_flag, "possible_additional_cost")
        self.assertIn("management_fee_amount", result.monthly_cost_missing_items)

    def test_included_fee_amount_is_not_added_again(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "18000"
        info.management_fee_amount = "1000"
        info.management_fee_included = True
        info.rates_amount = "500"
        info.rates_included = True

        result = self.service.assess(info, max_budget=22000)

        self.assertEqual(result.known_monthly_cost, 18000)

    def test_explicit_separate_known_fee_is_added(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "18000"
        info.management_fee_amount = "1000"
        info.management_fee_included = False
        info.rates_amount = "500"
        info.rates_included = False

        result = self.service.assess(info, max_budget=22000)

        self.assertEqual(result.known_monthly_cost, 19500)

    def test_unverifiable_amount_over_budget_stays_incomplete(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "30000"
        info.management_fee_included = True
        info.rates_included = True

        result = self.service.assess(
            info,
            max_budget=22000,
            source_text="Rent amount to be confirmed with the agent.",
        )

        self.assertEqual(result.cost_risk_flag, "incomplete")
        self.assertNotIn("exceeds", result.summary.lower())

    def test_source_backed_amount_can_be_marked_over_budget(self):
        info = self.candidate.extracted_info
        info.monthly_rent = "HKD 30,000"
        info.management_fee_included = True
        info.rates_included = True

        result = self.service.assess(
            info,
            max_budget=22000,
            source_text="Monthly rent: HKD 30,000, including management fees and rates.",
        )

        self.assertEqual(result.cost_risk_flag, "over_budget")
