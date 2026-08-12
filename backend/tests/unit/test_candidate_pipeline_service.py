from __future__ import annotations

import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_pipeline_service import CandidatePipelineService
from tests.helpers import build_candidate, build_project, build_user


class _FakeSession:
    def __init__(self):
        self.flush = AsyncMock()
        self.commit = AsyncMock()


class CandidatePipelineServiceTests(IsolatedAsyncioTestCase):
    async def test_budget_reassessment_does_not_call_extraction_or_legal_enrichment(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        service = CandidatePipelineService()
        service.extraction_service.extract = AsyncMock()
        service.clause_service.attach_legal_references = AsyncMock()
        db = _FakeSession()

        await service.reassess_for_budget(db=db, project=project, candidate=candidate)

        service.extraction_service.extract.assert_not_awaited()
        service.clause_service.attach_legal_references.assert_not_awaited()
        db.flush.assert_awaited_once()

    async def test_full_analysis_enters_assessing_before_deterministic_rules(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        service = CandidatePipelineService()
        extracted = candidate.extracted_info
        service.extraction_service.extract = AsyncMock(return_value=extracted)
        service.clause_service.attach_legal_references = AsyncMock()
        db = _FakeSession()

        await service.assess_candidate(db=db, project=project, candidate=candidate)

        self.assertEqual(candidate.processing_stage, "assessing")
        db.commit.assert_awaited_once()

    async def test_reassessment_preserves_user_decision_without_overwriting_system_status(self):
        project = build_project(build_user())
        service = CandidatePipelineService()
        service.clause_service.attach_legal_references = AsyncMock()

        for user_decision in ("shortlisted", "rejected"):
            with self.subTest(user_decision=user_decision):
                candidate = build_candidate(
                    project,
                    status="follow_up",
                    user_decision=user_decision,
                    next_best_action="schedule_viewing",
                )
                db = _FakeSession()

                await service.reassess_for_budget(
                    db=db,
                    project=project,
                    candidate=candidate,
                )

                self.assertEqual(candidate.user_decision, user_decision)
                self.assertEqual(candidate.status, "needs_info")
                self.assertEqual(candidate.candidate_assessment.status, "needs_info")
