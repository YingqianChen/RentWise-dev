"""Candidate ingestion and assessment pipeline."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CandidateAssessment, CandidateExtractedInfo, CandidateListing, ClauseAssessment, CostAssessment, SearchProject
from .candidate_assessment_service import CandidateAssessmentService
from .candidate_field_evidence_service import CandidateFieldEvidenceService
from .clause_assessment_service import ClauseAssessmentService
from .cost_assessment_service import CostAssessmentService
from .extraction_service import ExtractionService


class CandidatePipelineService:
    """Runs the full assessment pipeline for a candidate."""

    def __init__(self) -> None:
        self.extraction_service = ExtractionService()
        self.field_evidence_service = CandidateFieldEvidenceService()
        self.cost_service = CostAssessmentService()
        self.clause_service = ClauseAssessmentService()
        self.candidate_service = CandidateAssessmentService()

    async def assess_candidate(
        self,
        db: AsyncSession,
        project: SearchProject,
        candidate: CandidateListing,
    ) -> CandidateListing:
        """Create or refresh all assessment records for a candidate."""
        extraction_result = await self.extraction_service.extract_with_evidence(candidate)
        extracted_info = extraction_result.extracted_info
        candidate.processing_stage = "assessing"
        candidate.processing_error = None
        candidate.processing_error_code = None
        await db.commit()

        await self.field_evidence_service.replace_system_results(
            db,
            candidate_id=candidate.id,
            facts=extraction_result.field_facts,
        )

        await self._assess_from_extracted(
            db=db,
            project=project,
            candidate=candidate,
            extracted_info=extracted_info,
            clause_assessment=None,
        )
        return candidate

    async def reassess_for_budget(
        self,
        db: AsyncSession,
        project: SearchProject,
        candidate: CandidateListing,
    ) -> CandidateListing:
        """Recalculate budget-sensitive rules without calling extraction or legal enrichment."""
        if candidate.extracted_info is None or candidate.clause_assessment is None:
            raise ValueError("Budget reassessment requires completed extracted and clause records.")

        await self._assess_from_extracted(
            db=db,
            project=project,
            candidate=candidate,
            extracted_info=candidate.extracted_info,
            clause_assessment=candidate.clause_assessment,
        )
        return candidate

    async def reassess_after_field_change(
        self,
        db: AsyncSession,
        project: SearchProject,
        candidate: CandidateListing,
    ) -> CandidateListing:
        """Recalculate local assessments without extraction, legal RAG, or maps."""
        if candidate.extracted_info is None:
            raise ValueError("Field reassessment requires an extracted snapshot.")

        clause_assessment = self.clause_service.assess(
            candidate.extracted_info,
            move_in_target=project.move_in_target,
        )
        await self._assess_from_extracted(
            db=db,
            project=project,
            candidate=candidate,
            extracted_info=candidate.extracted_info,
            clause_assessment=clause_assessment,
        )
        return candidate

    async def _assess_from_extracted(
        self,
        *,
        db: AsyncSession,
        project: SearchProject,
        candidate: CandidateListing,
        extracted_info: CandidateExtractedInfo,
        clause_assessment: ClauseAssessment | None,
    ) -> None:
        cost_assessment = self.cost_service.assess(
            extracted_info,
            max_budget=project.max_budget,
        )
        if clause_assessment is None:
            clause_assessment = self.clause_service.assess(
                extracted_info,
                move_in_target=project.move_in_target,
            )
            await self.clause_service.attach_legal_references(clause_assessment)
        candidate_assessment = self.candidate_service.assess(
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            preferred_districts=project.preferred_districts,
        )

        self._apply_assessment_records(
            candidate=candidate,
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            candidate_assessment=candidate_assessment,
        )

        await db.flush()

    async def generate_candidate_name(self, candidate: CandidateListing) -> str:
        """Generate a user-facing candidate name from extracted info and source text."""
        extracted_info = candidate.extracted_info
        if extracted_info is None:
            extracted_info = await self.extraction_service.extract(candidate)
        return await self.extraction_service.generate_listing_name(
            extracted_info=extracted_info,
            combined_text=candidate.combined_text or "",
        )

    def _apply_assessment_records(
        self,
        candidate: CandidateListing,
        extracted_info: CandidateExtractedInfo,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        candidate_assessment: CandidateAssessment,
    ) -> None:
        """Replace candidate one-to-one assessment records."""
        candidate.extracted_info = extracted_info
        candidate.cost_assessment = cost_assessment
        candidate.clause_assessment = clause_assessment
        candidate.candidate_assessment = candidate_assessment
        candidate.status = candidate_assessment.status
