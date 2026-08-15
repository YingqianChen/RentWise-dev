from __future__ import annotations

import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import projects as projects_api
from app.schemas.project import ProjectUpdate
from tests.helpers import build_candidate, build_project, build_user


class FakeAsyncSession:
    def __init__(self):
        self.delete = AsyncMock()
        self.flush = AsyncMock()
        self.refresh = AsyncMock()


class ProjectRouteTests(IsolatedAsyncioTestCase):
    async def test_update_project_budget_updates_owned_project(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()
        execute_results = [project, [candidate]]

        async def fake_execute(*_args, **_kwargs):
            class _Result:
                def __init__(self, value):
                    self.value = value

                def scalar_one_or_none(self):
                    return self.value

                def scalars(self):
                    class _Scalars:
                        def __init__(self, values):
                            self.values = values

                        def all(self):
                            return self.values

                    return _Scalars(self.value)

            return _Result(execute_results.pop(0))

        async def fake_refresh(obj):
            return obj

        db.execute = fake_execute
        db.refresh = fake_refresh

        with (
            patch.object(
                projects_api.pipeline_service,
                "reassess_for_project_preferences",
                AsyncMock(),
            ) as budget_mock,
            patch.object(
                projects_api.pipeline_service,
                "assess_candidate",
                AsyncMock(),
            ) as extraction_mock,
        ):
            response = await projects_api.update_project(
                project_id=project.id,
                project_data=ProjectUpdate(max_budget=25000),
                current_user=user,
                db=db,
            )

        self.assertEqual(project.max_budget, 25000)
        self.assertEqual(response.max_budget, 25000)
        budget_mock.assert_awaited_once_with(
            db=db,
            project=project,
            candidate=candidate,
            move_in_target_changed=False,
        )
        extraction_mock.assert_not_awaited()
        db.flush.assert_awaited_once()

    async def test_update_budget_skips_failed_candidate_with_stale_records(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        candidate.processing_stage = "failed"
        db = FakeAsyncSession()
        execute_results = [project, [candidate]]

        async def fake_execute(*_args, **_kwargs):
            class _Result:
                def __init__(self, value):
                    self.value = value

                def scalar_one_or_none(self):
                    return self.value

                def scalars(self):
                    class _Scalars:
                        def __init__(self, values):
                            self.values = values

                        def all(self):
                            return self.values

                    return _Scalars(self.value)

            return _Result(execute_results.pop(0))

        db.execute = fake_execute

        with patch.object(
            projects_api.pipeline_service,
            "reassess_for_project_preferences",
            AsyncMock(),
        ) as budget_mock:
            await projects_api.update_project(
                project_id=project.id,
                project_data=ProjectUpdate(max_budget=25000),
                current_user=user,
                db=db,
            )

        budget_mock.assert_not_awaited()

    async def test_update_project_preferences_reassesses_without_extraction(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()
        execute_results = [project, [candidate]]

        async def fake_execute(*_args, **_kwargs):
            class _Result:
                def __init__(self, value):
                    self.value = value

                def scalar_one_or_none(self):
                    return self.value

                def scalars(self):
                    class _Scalars:
                        def __init__(self, values):
                            self.values = values

                        def all(self):
                            return self.values

                    return _Scalars(self.value)

            return _Result(execute_results.pop(0))

        db.execute = fake_execute

        with (
            patch.object(
                projects_api.pipeline_service,
                "reassess_for_project_preferences",
                AsyncMock(),
            ) as preference_mock,
            patch.object(
                projects_api.pipeline_service,
                "assess_candidate",
                AsyncMock(),
            ) as extraction_mock,
        ):
            response = await projects_api.update_project(
                project_id=project.id,
                project_data=ProjectUpdate(
                    preferred_districts=["Kowloon"],
                    move_in_target="2026-06-01",
                    must_have=[" Furnished ", "furnished"],
                    deal_breakers=["Shared bathroom"],
                ),
                current_user=user,
                db=db,
            )

        self.assertEqual(response.preferred_districts, ["Kowloon"])
        self.assertEqual(project.must_have, ["Furnished"])
        self.assertEqual(project.deal_breakers, ["Shared bathroom"])
        preference_mock.assert_awaited_once_with(
            db=db,
            project=project,
            candidate=candidate,
            move_in_target_changed=True,
        )
        extraction_mock.assert_not_awaited()

    def test_project_preference_lists_are_normalized_and_limited(self):
        project_data = ProjectUpdate(
            preferred_districts=[" Wan Chai ", "wan chai", ""],
            must_have=["Furnished", " furnished "],
            deal_breakers=["No lift"],
        )

        self.assertEqual(project_data.preferred_districts, ["Wan Chai"])
        self.assertEqual(project_data.must_have, ["Furnished"])
        self.assertEqual(project_data.deal_breakers, ["No lift"])

        with self.assertRaises(ValueError):
            ProjectUpdate(preferred_districts=[f"District {index}" for index in range(21)])

    async def test_delete_project_deletes_owned_project(self):
        user = build_user()
        project = build_project(user)
        db = FakeAsyncSession()

        async def fake_execute(*_args, **_kwargs):
            class _Result:
                @staticmethod
                def scalar_one_or_none():
                    return project

            return _Result()

        db.execute = fake_execute

        response = await projects_api.delete_project(
            project_id=project.id,
            current_user=user,
            db=db,
        )

        self.assertIsNone(response)
        db.delete.assert_awaited_once_with(project)
        db.flush.assert_awaited_once()
