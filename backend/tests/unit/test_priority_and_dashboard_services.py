from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.dashboard_service import DashboardService
from app.services.priority_service import PriorityService
from tests.helpers import build_candidate, build_project, build_user


class PriorityAndDashboardServiceTests(TestCase):
    def test_verify_cost_candidate_can_rank_above_schedule_viewing_when_upside_is_high(self):
        user = build_user()
        project = build_project(user)

        verify_cost_candidate = build_candidate(
            project,
            name="Potential but unclear",
            status="needs_info",
            next_best_action="verify_cost",
        )
        verify_cost_candidate.candidate_assessment.potential_value_level = "high"
        verify_cost_candidate.candidate_assessment.information_gain_level = "high"
        verify_cost_candidate.candidate_assessment.critical_uncertainty_level = "high"
        verify_cost_candidate.candidate_assessment.recommendation_confidence = "low"

        stable_candidate = build_candidate(
            project,
            name="Stable option",
            status="follow_up",
            next_best_action="schedule_viewing",
        )
        stable_candidate.candidate_assessment.potential_value_level = "medium"
        stable_candidate.candidate_assessment.information_gain_level = "low"
        stable_candidate.candidate_assessment.critical_uncertainty_level = "low"
        stable_candidate.candidate_assessment.recommendation_confidence = "high"
        stable_candidate.cost_assessment.cost_risk_flag = "none"
        stable_candidate.cost_assessment.monthly_cost_confidence = "high"

        ranked = PriorityService().rank(
            [
                verify_cost_candidate.candidate_assessment,
                stable_candidate.candidate_assessment,
            ]
        )

        self.assertEqual(ranked[0][0], verify_cost_candidate.id)

    def test_investigation_items_become_specific_checklist_tasks(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project, next_best_action="verify_cost")

        items = DashboardService().build_investigation_items([candidate])

        titles = [item.title for item in items]
        self.assertTrue(any("management fee" in title.lower() for title in titles))
        self.assertTrue(any("rates" in title.lower() for title in titles))
        self.assertTrue(any("repair responsibility" in title.lower() for title in titles))

    def test_investigation_items_group_shared_blockers_across_candidates(self):
        user = build_user()
        project = build_project(user)
        first = build_candidate(project, name="Kai Tak $16.8k", next_best_action="verify_cost")
        second = build_candidate(project, name="PE $13k", next_best_action="verify_cost")

        items = DashboardService().build_investigation_items([first, second])

        management_items = [item for item in items if "management fee" in item.title.lower()]
        repair_items = [item for item in items if "repair responsibility" in item.title.lower()]

        self.assertEqual(len(management_items), 1)
        self.assertIn("kai tak $16.8k", management_items[0].title.lower())
        self.assertIn("pe $13k", management_items[0].title.lower())
        self.assertIn("kai tak $16.8k", management_items[0].question.lower())
        self.assertIn("pe $13k", management_items[0].question.lower())

        self.assertEqual(len(repair_items), 1)
        self.assertIn("kai tak $16.8k", repair_items[0].title.lower())
        self.assertIn("pe $13k", repair_items[0].title.lower())

    def test_priority_cards_include_backend_reason(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project, next_best_action="verify_cost")

        cards = DashboardService().build_priority_candidates([candidate])

        self.assertEqual(len(cards), 1)
        self.assertIn("confirm", cards[0].reason.lower())

    def test_failed_candidate_with_old_assessments_is_excluded_from_dashboard_work(self):
        project = build_project(build_user())
        failed = build_candidate(project, name="Stale result")
        failed.processing_stage = "failed"

        service = DashboardService()
        stats = service.build_stats([failed])

        self.assertEqual(service.build_priority_candidates([failed]), [])
        self.assertEqual(service.build_investigation_items([failed]), [])
        self.assertEqual(stats.analysis_failed, 1)
        self.assertIn(
            "retry",
            service.build_current_advice(project, stats, [], []).lower(),
        )

    def test_processing_candidate_is_counted_but_not_ranked(self):
        project = build_project(build_user())
        processing = build_candidate(project)
        processing.processing_stage = "assessing"

        service = DashboardService()
        stats = service.build_stats([processing])

        self.assertEqual(stats.processing, 1)
        self.assertEqual(service.build_priority_candidates([processing]), [])

    def test_legacy_candidate_without_field_contract_is_not_ranked(self):
        legacy = build_candidate(build_project(build_user()))
        legacy.field_facts = []

        service = DashboardService()

        self.assertEqual(service.build_priority_candidates([legacy]), [])
        self.assertEqual(service.build_investigation_items([legacy]), [])

    def test_top_level_recommendation_is_derived_from_assessment_state(self):
        user = build_user()
        project = build_project(user)

        shortlist_candidate = build_candidate(project, next_best_action="schedule_viewing", status="follow_up")
        shortlist_candidate.candidate_assessment.recommendation_confidence = "high"

        not_ready_candidate = build_candidate(project, next_best_action="verify_cost", status="needs_info")

        reject_candidate = build_candidate(project, next_best_action="reject", status="recommended_reject")

        self.assertEqual(
            shortlist_candidate.candidate_assessment.top_level_recommendation,
            "shortlist_recommendation",
        )
        self.assertEqual(
            not_ready_candidate.candidate_assessment.top_level_recommendation,
            "not_ready",
        )
        self.assertEqual(
            reject_candidate.candidate_assessment.top_level_recommendation,
            "likely_reject",
        )

    def test_stats_keep_system_recommendations_separate_from_user_decisions(self):
        project = build_project(build_user())
        system_reject_user_shortlisted = build_candidate(
            project,
            status="recommended_reject",
            user_decision="shortlisted",
            next_best_action="reject",
        )
        system_reject_user_shortlisted.candidate_assessment.status = "recommended_reject"

        system_follow_up_user_rejected = build_candidate(
            project,
            status="follow_up",
            user_decision="rejected",
            next_best_action="schedule_viewing",
        )
        system_follow_up_user_rejected.candidate_assessment.status = "follow_up"

        stats = DashboardService().build_stats(
            [system_reject_user_shortlisted, system_follow_up_user_rejected]
        )

        self.assertEqual(stats.recommended_reject, 1)
        self.assertEqual(stats.follow_up, 1)
        self.assertEqual(stats.shortlisted, 1)
        self.assertEqual(stats.rejected, 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
