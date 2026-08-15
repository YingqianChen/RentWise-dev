from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import dashboard as dashboard_api
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


class DashboardRouteTests(IsolatedAsyncioTestCase):
    async def test_get_dashboard_returns_graph_summary(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project, next_best_action="schedule_viewing", status="follow_up")
        db = FakeAsyncSession(_ListResult([candidate]))

        async def fake_get_project_for_user(project_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project

        run_mock = AsyncMock(
            return_value={
                "stats": {
                    "total": 1,
                    "new": 0,
                    "needs_info": 0,
                    "follow_up": 1,
                    "high_risk_pending": 0,
                    "recommended_reject": 0,
                    "shortlisted": 0,
                    "rejected": 0,
                },
                "current_advice": "Candidate A is ready for follow-up.",
                "priority_candidates": [
                    {
                        "id": candidate.id,
                        "name": candidate.name,
                        "status": candidate.status,
                        "potential_value_level": "high",
                        "completeness_level": "medium",
                        "next_best_action": "schedule_viewing",
                        "monthly_rent": "18000",
                        "district": "Wan Chai",
                        "reason": "Candidate A is stable enough to view next.",
                        "priority_score": 0.82,
                    }
                ],
                "open_items": [],
            }
        )
        sync_mock = AsyncMock(return_value=([], []))

        with (
            patch.object(dashboard_api, "get_project_for_user", fake_get_project_for_user),
            patch.object(dashboard_api.investigation_service, "run", run_mock),
            patch.object(dashboard_api.investigation_service, "sync_items", sync_mock),
        ):
            response = await dashboard_api.get_dashboard(
                project_id=project.id,
                current_user=user,
                db=db,
            )

        self.assertEqual(response.project_id, project.id)
        self.assertEqual(response.stats.follow_up, 1)
        self.assertEqual(response.current_advice, "Candidate A is ready for follow-up.")
        self.assertEqual(response.priority_candidates[0].id, candidate.id)
        self.assertEqual(response.closed_investigation_items, [])
        self.assertIsInstance(response.generated_at, datetime)
        self.assertEqual(response.generated_at.tzinfo, timezone.utc)
        run_mock.assert_awaited_once_with(project=project, candidates=[candidate])
        sync_mock.assert_awaited_once_with(
            db=db,
            project=project,
            generated_items=[],
        )
