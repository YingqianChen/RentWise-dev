"""Persist candidate analysis state transitions for synchronous API requests."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CandidateListing, SearchProject
from .analysis_errors import AnalysisError, analysis_error
from .candidate_pipeline_service import CandidatePipelineService

logger = logging.getLogger(__name__)


async def run_candidate_analysis(
    *,
    db: AsyncSession,
    project: SearchProject,
    candidate: CandidateListing,
    pipeline: CandidatePipelineService,
) -> bool:
    """Run analysis and persist a completed or safely classified failed state."""
    candidate.processing_stage = "extracting"
    candidate.processing_error = None
    candidate.processing_error_code = None
    await db.commit()

    try:
        await pipeline.assess_candidate(db=db, project=project, candidate=candidate)
    except AnalysisError as exc:
        logger.warning("Candidate analysis failed with code %s", exc.code)
        await db.rollback()
        await _persist_failed_state(db=db, candidate_id=candidate.id, failure=exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive classification boundary
        logger.exception("Candidate analysis failed unexpectedly", exc_info=exc)
        await db.rollback()
        failure = analysis_error("analysis_internal_error", retryable=True)
        await _persist_failed_state(db=db, candidate_id=candidate.id, failure=failure)
        return False

    candidate.processing_stage = "completed"
    candidate.processing_error = None
    candidate.processing_error_code = None
    await db.commit()
    return True


async def _persist_failed_state(
    *,
    db: AsyncSession,
    candidate_id: UUID,
    failure: AnalysisError,
) -> None:
    await db.execute(
        update(CandidateListing)
        .where(CandidateListing.id == candidate_id)
        .values(
            processing_stage="failed",
            processing_error=failure.user_message,
            processing_error_code=failure.code,
            status="needs_info",
        )
    )
    await db.commit()
