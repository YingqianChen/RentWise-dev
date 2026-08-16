from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import comparison as comparison_api
from app.schemas.comparison import CompareAgentBriefing
from tests.helpers import build_candidate, build_project, build_user


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarsResult(self._values)


class FakeAsyncSession:
    def __init__(self, result):
        self._result = result

    async def execute(self, *_args, **_kwargs):
        return self._result


class CompareRouteTests(IsolatedAsyncioTestCase):
    async def test_compare_route_returns_grouped_workspace(self):
        user = build_user()
        project = build_project(user)
        candidate_a = build_candidate(project, name="Candidate A", status="follow_up", next_best_action="schedule_viewing")
        candidate_a.cost_assessment.monthly_cost_confidence = "high"
        candidate_a.cost_assessment.cost_risk_flag = "none"
        candidate_a.clause_assessment.clause_risk_flag = "none"
        candidate_a.candidate_assessment.recommendation_confidence = "high"
        candidate_a.candidate_assessment.critical_uncertainty_level = "low"
        candidate_b = build_candidate(project, name="Candidate B", status="needs_info", next_best_action="verify_cost")
        db = FakeAsyncSession(_ListResult([candidate_a, candidate_b]))

        async def fake_get_project_for_user(project_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project

        async def fake_build_briefing(**_kwargs):
            return CompareAgentBriefing(
                current_take="Candidate A is the current lead.",
                why_now="It is easier to trust today.",
                what_could_change="Candidate B could still move up if costs are confirmed.",
                today_s_move="Contact Candidate A first.",
                confidence_note="This is still a working compare, not a final verdict.",
            )

        with (
            patch.object(comparison_api, "get_project_for_user", fake_get_project_for_user),
            patch.object(comparison_api.comparison_briefing_service, "build", fake_build_briefing),
        ):
            response = await comparison_api.compare_candidates(
                project_id=project.id,
                request=comparison_api.ComparisonRequest(candidate_ids=[candidate_a.id, candidate_b.id]),
                current_user=user,
                db=db,
            )

        self.assertEqual(response.project_id, project.id)
        self.assertEqual(response.selected_count, 2)
        self.assertIsInstance(response.generated_at, datetime)
        self.assertEqual(response.generated_at.tzinfo, timezone.utc)
        self.assertTrue(response.summary.headline)
        self.assertTrue(response.agent_briefing.current_take)
        self.assertIsNotNone(response.groups.best_current_option)

    async def test_compare_route_rejects_processing_or_failed_analysis(self):
        user = build_user()
        project = build_project(user)
        completed = build_candidate(project, name="Completed")
        failed = build_candidate(project, name="Failed")
        failed.processing_stage = "failed"
        db = FakeAsyncSession(_ListResult([completed, failed]))

        async def fake_get_project_for_user(*_args, **_kwargs):
            return project

        with patch.object(comparison_api, "get_project_for_user", fake_get_project_for_user):
            with self.assertRaises(HTTPException) as exc_info:
                await comparison_api.compare_candidates(
                    project_id=project.id,
                    request=comparison_api.ComparisonRequest(
                        candidate_ids=[completed.id, failed.id]
                    ),
                    current_user=user,
                    db=db,
                )

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("analysis", exc_info.exception.detail.lower())

    async def test_compare_route_rejects_more_than_five_unique_candidates(self):
        user = build_user()
        project = build_project(user)
        candidates = [build_candidate(project, name=f"Candidate {index}") for index in range(6)]
        db = FakeAsyncSession(_ListResult(candidates))

        async def fake_get_project_for_user(*_args, **_kwargs):
            return project

        with patch.object(comparison_api, "get_project_for_user", fake_get_project_for_user):
            with self.assertRaises(HTTPException) as exc_info:
                await comparison_api.compare_candidates(
                    project_id=project.id,
                    request=comparison_api.ComparisonRequest(
                        candidate_ids=[candidate.id for candidate in candidates]
                    ),
                    current_user=user,
                    db=db,
                )

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertIn("between 2 and 5", exc_info.exception.detail)

    async def test_compare_route_rejects_legacy_candidate_without_field_contract(self):
        user = build_user()
        project = build_project(user)
        current = build_candidate(project, name="Current")
        legacy = build_candidate(project, name="Legacy")
        legacy.field_facts = []
        db = FakeAsyncSession(_ListResult([current, legacy]))

        async def fake_get_project_for_user(*_args, **_kwargs):
            return project

        with patch.object(comparison_api, "get_project_for_user", fake_get_project_for_user):
            with self.assertRaises(HTTPException) as exc_info:
                await comparison_api.compare_candidates(
                    project_id=project.id,
                    request=comparison_api.ComparisonRequest(
                        candidate_ids=[current.id, legacy.id]
                    ),
                    current_user=user,
                    db=db,
                )

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("legacy", exc_info.exception.detail.lower())


if __name__ == "__main__":
    import unittest

    unittest.main()
