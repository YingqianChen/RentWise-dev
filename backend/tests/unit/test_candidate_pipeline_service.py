from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_pipeline_service import CandidatePipelineService
from tests.helpers import build_candidate, build_project, build_user


class _FakeScalarResult:
    def __init__(self, records):
        self.records = records

    def scalars(self):
        return self

    def all(self):
        return self.records


class _FakeSession:
    def __init__(self, field_facts=None):
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.execute = AsyncMock(return_value=_FakeScalarResult(field_facts or []))


class CandidatePipelineServiceTests(IsolatedAsyncioTestCase):
    async def test_budget_reassessment_does_not_call_extraction_or_legal_enrichment(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        service = CandidatePipelineService()
        service.extraction_service.extract_with_evidence = AsyncMock()
        service.clause_service.attach_legal_references = AsyncMock()
        db = _FakeSession()

        await service.reassess_for_budget(db=db, project=project, candidate=candidate)

        service.extraction_service.extract_with_evidence.assert_not_awaited()
        service.clause_service.attach_legal_references.assert_not_awaited()
        db.flush.assert_awaited_once()

    async def test_full_analysis_enters_assessing_before_deterministic_rules(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        service = CandidatePipelineService()
        extracted = candidate.extracted_info
        service.extraction_service.extract_with_evidence = AsyncMock(
            return_value=SimpleNamespace(extracted_info=extracted, field_facts=())
        )
        service.field_evidence_service.replace_system_results = AsyncMock()
        service.clause_service.attach_legal_references = AsyncMock()
        db = _FakeSession()

        await service.assess_candidate(db=db, project=project, candidate=candidate)

        self.assertEqual(candidate.processing_stage, "assessing")
        db.commit.assert_awaited_once()
        service.field_evidence_service.replace_system_results.assert_awaited_once_with(
            db,
            candidate_id=candidate.id,
            facts=(),
        )

    async def test_reanalysis_assessment_uses_user_field_actions(self):
        project = build_project(build_user())

        for action, user_value, expected_rent, expected_cost in (
            ("corrected", 20000, "20000", 20000),
            ("marked_unknown", None, None, None),
        ):
            with self.subTest(action=action):
                candidate = build_candidate(project)
                rent_fact = next(
                    fact for fact in candidate.field_facts if fact.field_key == "monthly_rent"
                )
                rent_fact.user_action = action
                rent_fact.user_value = user_value
                candidate.extracted_info.monthly_rent = "18000"

                service = CandidatePipelineService()
                service.extraction_service.extract_with_evidence = AsyncMock(
                    return_value=SimpleNamespace(
                        extracted_info=candidate.extracted_info,
                        field_facts=(),
                    )
                )
                service.field_evidence_service.replace_system_results = AsyncMock()
                db = _FakeSession(candidate.field_facts)

                await service.assess_candidate(db=db, project=project, candidate=candidate)

                self.assertEqual(candidate.extracted_info.monthly_rent, expected_rent)
                self.assertEqual(candidate.cost_assessment.known_monthly_cost, expected_cost)

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

    async def test_field_change_reassessment_is_local_only(self):
        project = build_project(build_user())
        candidate = build_candidate(project)
        service = CandidatePipelineService()
        service.extraction_service.extract_with_evidence = AsyncMock()
        service.clause_service.attach_legal_references = AsyncMock()
        db = _FakeSession()

        await service.reassess_after_field_change(
            db=db,
            project=project,
            candidate=candidate,
        )

        service.extraction_service.extract_with_evidence.assert_not_awaited()
        service.clause_service.attach_legal_references.assert_not_awaited()
        db.commit.assert_not_awaited()
        db.flush.assert_awaited_once()
