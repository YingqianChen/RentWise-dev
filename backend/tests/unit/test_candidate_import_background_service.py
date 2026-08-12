from __future__ import annotations

import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.analysis_errors import AnalysisError
from app.services.candidate_import_background_service import CandidateImportBackgroundService
from tests.helpers import build_candidate, build_project, build_user


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, candidate):
        self.candidate = candidate
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(self.candidate)


class CandidateImportBackgroundServiceTests(IsolatedAsyncioTestCase):
    async def test_structured_analysis_error_is_persisted_without_internal_details(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        candidate.source_assets = []
        db = _FakeSession(candidate)
        service = CandidateImportBackgroundService(lambda: db)

        with (
            patch.object(service, "_load_candidate", AsyncMock(return_value=candidate)),
            patch.object(
                service.pipeline,
                "assess_candidate",
                AsyncMock(
                    side_effect=AnalysisError(
                        code="llm_not_configured",
                        user_message="Analysis service is not configured. Your source information is saved.",
                        retryable=False,
                    )
                ),
            ),
        ):
            await service.process_candidate_import(
                project_id=project.id,
                candidate_id=candidate.id,
                should_autoname=False,
            )

        self.assertEqual(candidate.processing_stage, "failed")
        self.assertEqual(candidate.processing_error_code, "llm_not_configured")
        self.assertNotIn("API", candidate.processing_error)
        self.assertNotIn("GROQ", candidate.processing_error)
        db.rollback.assert_awaited_once()

    async def test_no_usable_text_has_stable_error_code(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        candidate.raw_listing_text = None
        candidate.raw_chat_text = None
        candidate.raw_note_text = None
        candidate.combined_text = None
        candidate.source_assets = []
        db = _FakeSession(candidate)
        service = CandidateImportBackgroundService(lambda: db)
        assess_mock = AsyncMock()

        with (
            patch.object(service, "_load_candidate", AsyncMock(return_value=candidate)),
            patch.object(service.pipeline, "assess_candidate", assess_mock),
        ):
            await service.process_candidate_import(
                project_id=project.id,
                candidate_id=candidate.id,
                should_autoname=False,
            )

        self.assertEqual(candidate.processing_stage, "failed")
        self.assertEqual(candidate.processing_error_code, "no_usable_text")
        assess_mock.assert_not_awaited()
