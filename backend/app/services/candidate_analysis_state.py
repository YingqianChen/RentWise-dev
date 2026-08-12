"""Single source of truth for whether candidate analysis may be consumed."""

from __future__ import annotations

from ..db.models import CandidateListing


PROCESSING_STAGES = {"queued", "running_ocr", "extracting", "assessing"}


def has_usable_analysis(candidate: CandidateListing) -> bool:
    """Return true only when the current analysis completed with every required record."""
    return candidate.processing_stage == "completed" and all(
        record is not None
        for record in (
            candidate.extracted_info,
            candidate.cost_assessment,
            candidate.clause_assessment,
            candidate.candidate_assessment,
        )
    )
