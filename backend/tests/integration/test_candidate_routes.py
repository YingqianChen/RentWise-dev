from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks
from fastapi import HTTPException
from starlette.datastructures import UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import candidates as candidates_api
from app.db.models import CandidateSourceAsset
from tests.helpers import build_candidate, build_project, build_user


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class FakeAsyncSession:
    def __init__(self, execute_results=None):
        self.execute_results = list(execute_results or [])
        self.added = []
        self.delete = AsyncMock()
        self.flush = AsyncMock()

    async def execute(self, *_args, **_kwargs):
        if not self.execute_results:
            raise AssertionError("Unexpected execute() call in test")
        return self.execute_results.pop(0)

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        if hasattr(obj, "status") and getattr(obj, "status", None) is None:
            obj.status = "new"
        if hasattr(obj, "user_decision") and getattr(obj, "user_decision", None) is None:
            obj.user_decision = "undecided"
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now

    def add_all(self, objects):
        for obj in objects:
            self.add(obj)


class CandidateRouteTests(IsolatedAsyncioTestCase):
    async def test_import_candidate_queues_background_processing(self):
        user = build_user()
        project = build_project(user)
        db = FakeAsyncSession(execute_results=[_ScalarResult(0)])

        async def fake_get_project_for_user(project_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project
        background_tasks = BackgroundTasks()

        with (
            patch.object(candidates_api, "get_project_for_user", fake_get_project_for_user),
        ):
            response = await candidates_api.import_candidate(
                project_id=project.id,
                background_tasks=background_tasks,
                raw_listing_text="Rent 18000 in Wan Chai",
                current_user=user,
                db=db,
            )

        self.assertEqual(response.project_id, project.id)
        self.assertEqual(response.name, "Candidate 1")
        self.assertEqual(response.processing_stage, "queued")
        self.assertIsNone(response.candidate_assessment)
        self.assertEqual(len(background_tasks.tasks), 1)

    async def test_import_candidate_keeps_user_supplied_name(self):
        user = build_user()
        project = build_project(user)
        db = FakeAsyncSession()
        background_tasks = BackgroundTasks()

        async def fake_get_project_for_user(project_id, current_user, session):
            return project

        with (
            patch.object(candidates_api, "get_project_for_user", fake_get_project_for_user),
        ):
            response = await candidates_api.import_candidate(
                project_id=project.id,
                background_tasks=background_tasks,
                name="User title",
                raw_listing_text="Rent 18000 in Wan Chai",
                current_user=user,
                db=db,
            )

        self.assertEqual(response.name, "User title")
        self.assertEqual(response.processing_stage, "queued")
        self.assertEqual(len(background_tasks.tasks), 1)

    async def test_import_candidate_accepts_ocr_images(self):
        user = build_user()
        project = build_project(user)
        db = FakeAsyncSession(execute_results=[_ScalarResult(0)])
        background_tasks = BackgroundTasks()
        upload = UploadFile(filename="listing.png", file=BytesIO(b"fake-image"))
        upload.headers = {}

        async def fake_get_project_for_user(project_id, current_user, session):
            return project

        with (
            patch.object(candidates_api, "get_project_for_user", fake_get_project_for_user),
            patch.object(
                candidates_api.candidate_import_service,
                "prepare_uploaded_images",
                AsyncMock(
                    return_value=[
                        CandidateSourceAsset(
                            id=uuid.uuid4(),
                            candidate_id=uuid.uuid4(),
                            storage_provider="local",
                            storage_key="candidate_uploads/test/listing.png",
                            original_filename="listing.png",
                            content_type="image/png",
                            file_size=10,
                            ocr_status="pending",
                            ocr_text=None,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                    ]
                ),
            ),
        ):
            response = await candidates_api.import_candidate(
                project_id=project.id,
                background_tasks=background_tasks,
                uploaded_images=[upload],
                current_user=user,
                db=db,
            )

        self.assertEqual(response.source_type, "image_upload")
        self.assertEqual(len(response.source_assets), 1)
        self.assertEqual(response.processing_stage, "queued")
        self.assertEqual(response.processing_error, "Waiting for OCR to read the uploaded images.")
        self.assertEqual(len(background_tasks.tasks), 1)

    async def test_reassess_candidate_runs_pipeline(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()
        assess_mock = AsyncMock()

        async def fake_get_candidate_for_project_user(project_id, candidate_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(candidate_id, candidate.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project, candidate

        with (
            patch.object(candidates_api, "get_candidate_for_project_user", fake_get_candidate_for_project_user),
            patch.object(candidates_api.pipeline_service, "assess_candidate", assess_mock),
        ):
            response = await candidates_api.reassess_candidate(
                project_id=project.id,
                candidate_id=candidate.id,
                current_user=user,
                db=db,
            )

        self.assertEqual(response.id, candidate.id)
        assess_mock.assert_awaited_once_with(db=db, project=project, candidate=candidate)
        db.flush.assert_awaited_once()

    async def test_update_candidate_with_text_changes_reruns_pipeline(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()
        assess_mock = AsyncMock()

        async def fake_get_candidate_for_project_user(project_id, candidate_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(candidate_id, candidate.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project, candidate

        with (
            patch.object(candidates_api, "get_candidate_for_project_user", fake_get_candidate_for_project_user),
            patch.object(candidates_api.pipeline_service, "assess_candidate", assess_mock),
        ):
            response = await candidates_api.update_candidate(
                project_id=project.id,
                candidate_id=candidate.id,
                candidate_data=candidates_api.CandidateUpdate(
                    raw_listing_text="Updated listing text",
                    raw_chat_text="Updated chat text",
                ),
                current_user=user,
                db=db,
            )

        self.assertEqual(response.id, candidate.id)
        self.assertEqual(candidate.raw_listing_text, "Updated listing text")
        self.assertEqual(candidate.raw_chat_text, "Updated chat text")
        self.assertIn("Updated listing text", candidate.combined_text)
        assess_mock.assert_awaited_once_with(db=db, project=project, candidate=candidate)
        db.flush.assert_awaited_once()

    async def test_update_candidate_rejects_empty_text_payload(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()
        assess_mock = AsyncMock()

        async def fake_get_candidate_for_project_user(project_id, candidate_id, current_user, session):
            return project, candidate

        with (
            patch.object(candidates_api, "get_candidate_for_project_user", fake_get_candidate_for_project_user),
            patch.object(candidates_api.pipeline_service, "assess_candidate", assess_mock),
        ):
            with self.assertRaises(HTTPException) as exc_info:
                await candidates_api.update_candidate(
                    project_id=project.id,
                    candidate_id=candidate.id,
                    candidate_data=candidates_api.CandidateUpdate(
                        raw_listing_text="",
                        raw_chat_text="",
                        raw_note_text="",
                    ),
                    current_user=user,
                    db=db,
                )

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(exc_info.exception.detail, "At least one text field is required")
        assess_mock.assert_not_awaited()

    async def test_get_candidate_for_project_user_blocks_cross_project_candidate(self):
        user = build_user()
        project = build_project(user)
        db = FakeAsyncSession(execute_results=[_ScalarResult(None)])

        async def fake_get_project_for_user(project_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project

        with patch.object(candidates_api, "get_project_for_user", fake_get_project_for_user):
            with self.assertRaises(HTTPException) as exc_info:
                await candidates_api.get_candidate_for_project_user(
                    project_id=project.id,
                    candidate_id=uuid.uuid4(),
                    user=user,
                    db=db,
                )

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Candidate not found")

    async def test_delete_candidate_deletes_owned_candidate(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        db = FakeAsyncSession()

        async def fake_get_candidate_for_project_user(project_id, candidate_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(candidate_id, candidate.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project, candidate

        with patch.object(candidates_api, "get_candidate_for_project_user", fake_get_candidate_for_project_user):
            response = await candidates_api.delete_candidate(
                project_id=project.id,
                candidate_id=candidate.id,
                current_user=user,
                db=db,
            )

        self.assertIsNone(response)
        db.delete.assert_awaited_once_with(candidate)
        db.flush.assert_awaited_once()
