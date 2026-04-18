"""Candidate ingestion and assessment pipeline."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CandidateAssessment, CandidateExtractedInfo, CandidateListing, ClauseAssessment, CostAssessment, SearchProject
from .candidate_assessment_service import CandidateAssessmentService
from .clause_assessment_service import ClauseAssessmentService
from .cost_assessment_service import CostAssessmentService
from .extraction_service import ExtractionService


class CandidatePipelineService:
    """Runs the full assessment pipeline for a candidate."""

    def __init__(self) -> None:
        self.extraction_service = ExtractionService()
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
        extracted_info = await self.extraction_service.extract(candidate)
        cost_assessment = self.cost_service.assess(extracted_info, max_budget=project.max_budget)
        clause_assessment = self.clause_service.assess(
            extracted_info,
            move_in_target=project.move_in_target,
        )
        await self.clause_service.attach_legal_references(clause_assessment)
        candidate_assessment = self.candidate_service.assess(
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            max_budget=project.max_budget,
            preferred_districts=project.preferred_districts,
            must_have=project.must_have,
            deal_breakers=project.deal_breakers,
            move_in_target=project.move_in_target,
        )

        self._apply_assessment_records(
            candidate=candidate,
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            candidate_assessment=candidate_assessment,
        )

        await db.flush()
        return candidate

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

        if candidate.user_decision == "shortlisted":
            candidate.status = "shortlisted"
            candidate_assessment.status = "shortlisted"
        elif candidate.user_decision == "rejected":
            candidate.status = "recommended_reject"
            candidate_assessment.status = "recommended_reject"
        else:
            candidate.status = candidate_assessment.status
