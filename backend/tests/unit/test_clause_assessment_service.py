from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.clause_assessment_service import ClauseAssessmentService
from tests.helpers import build_candidate, build_project, build_user


class ClauseAssessmentServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = ClauseAssessmentService()
        self.user = build_user()
        self.project = build_project(self.user)

    def test_marks_explicit_landlord_repair_responsibility_as_clear(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.repair_responsibility = "Landlord handles major repairs and owner pays for broken appliances."

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.repair_responsibility_level, "clear")
        self.assertEqual(result.clause_risk_flag, "none")

    def test_marks_agency_repair_support_as_supported_but_unconfirmed(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.repair_responsibility = "I can contact the agency, they will pay for the repair."
        candidate.extracted_info.move_in_date = "2026-05-01"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.repair_responsibility_level, "supported_but_unconfirmed")
        self.assertEqual(result.clause_risk_flag, "needs_confirmation")
        self.assertIn("positive signal", result.summary.lower())

    def test_marks_tenant_heavy_repair_language_as_high_risk(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.repair_responsibility = "Tenant responsible for all repairs and maintenance."
        candidate.extracted_info.move_in_date = "2026-05-01"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.repair_responsibility_level, "tenant_heavy")
        self.assertEqual(result.clause_risk_flag, "high_risk")

    def test_treats_one_year_fixed_one_year_optional_as_standard(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.lease_term = "1 year fixed 1 year optional with break clause"
        candidate.extracted_info.move_in_date = "2026-05-01"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.lease_term_level, "standard")

    def test_treats_monthly_rolling_lease_as_unstable(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.lease_term = "Monthly rolling lease, can leave anytime"
        candidate.extracted_info.move_in_date = "2026-05-01"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.lease_term_level, "unstable")
        self.assertEqual(result.clause_risk_flag, "high_risk")

    def test_treats_same_month_move_in_as_fit(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.move_in_date = "Available from May 2026"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.move_in_date_level, "fit")

    def test_treats_later_month_move_in_as_mismatch(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.move_in_date = "Available from June 2026"

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.move_in_date_level, "mismatch")

    def test_treats_school_dorm_maintenance_note_as_clear_repair_signal(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.repair_responsibility = "School dorm, maintenance included and repairs are covered."

        result = self.service.assess(candidate.extracted_info, move_in_target=self.project.move_in_target)

        self.assertEqual(result.repair_responsibility_level, "clear")
        self.assertEqual(result.clause_risk_flag, "none")

    def test_treats_semester_start_note_as_fit_without_exact_date(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.move_in_date = "Can move in at semester start / 开学时入住"

        result = self.service.assess(candidate.extracted_info, move_in_target=None)

        self.assertEqual(result.move_in_date_level, "fit")

    def test_unmodeled_signals_cannot_fill_missing_clause_fields(self):
        candidate = build_candidate(self.project)
        candidate.extracted_info.repair_responsibility = None
        candidate.extracted_info.move_in_date = None
        candidate.extracted_info.decision_signals = [
            {
                "key": "repair_support_signal",
                "label": "Landlord covers repairs",
                "evidence": "The landlord handles repairs.",
            },
            {
                "key": "move_in_timing_signal",
                "label": "Available now",
                "evidence": "Available now.",
            },
        ]

        result = self.service.assess(
            candidate.extracted_info,
            move_in_target=self.project.move_in_target,
        )

        self.assertEqual(result.repair_responsibility_level, "unknown")
        self.assertEqual(result.move_in_date_level, "unknown")
