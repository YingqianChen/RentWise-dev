"""Comparison API endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.database import get_db
from ...db.models import CandidateListing, User
from ...schemas.comparison import ComparisonRequest, ComparisonResponse
from ...services.commute_service import CommuteService
from ...services.comparison_briefing_service import ComparisonBriefingService
from ...services.comparison_service import ComparisonService
from .auth import get_current_user
from .candidates import get_project_for_user

router = APIRouter()
comparison_service = ComparisonService()
comparison_briefing_service = ComparisonBriefingService()
commute_service = CommuteService()


def _candidate_query(project_id: UUID, candidate_ids: list[UUID]):
    return (
        select(CandidateListing)
        .options(
            selectinload(CandidateListing.extracted_info),
            selectinload(CandidateListing.cost_assessment),
            selectinload(CandidateListing.clause_assessment),
            selectinload(CandidateListing.candidate_assessment),
        )
        .where(
            CandidateListing.project_id == project_id,
            CandidateListing.id.in_(candidate_ids),
        )
    )


def _iter_group_cards(groups):
    """Iterate over all candidate cards across decision groups."""
    if groups.best_current_option:
        yield groups.best_current_option
    yield from groups.viable_alternatives
    yield from groups.not_ready_for_fair_comparison
    yield from groups.likely_drop


@router.post("/projects/{project_id}/compare", response_model=ComparisonResponse)
async def compare_candidates(
    project_id: UUID,
    request: ComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare a manually selected candidate set inside a single project."""
    project = await get_project_for_user(project_id, current_user, db)
    unique_ids = list(dict.fromkeys(request.candidate_ids))
    if len(unique_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least two candidates to compare.",
        )

    result = await db.execute(_candidate_query(project.id, unique_ids))
    candidates = result.scalars().all()

    if len(candidates) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more selected candidates were not found in this project.",
        )

    comparison = comparison_service.compare(project=project, candidates=candidates)

    # Compute commute evidence for all candidates in parallel
    candidates_by_id = {c.id: c for c in candidates}
    commute_tasks = {
        cid: commute_service.build_for_candidate(project, candidate)
        for cid, candidate in candidates_by_id.items()
    }
    commute_results = dict(zip(commute_tasks.keys(), await asyncio.gather(*commute_tasks.values())))

    # Attach commute evidence to all candidate cards in groups
    groups = comparison["groups"]
    for card in _iter_group_cards(groups):
        card.commute_evidence = commute_results.get(card.candidate_id)

    agent_briefing = await comparison_briefing_service.build(
        project=project,
        candidates=candidates,
        summary=comparison["summary"],
        groups=groups,
        key_differences=comparison["key_differences"],
        recommended_actions=comparison["recommended_next_actions"],
    )
    return ComparisonResponse(
        project_id=project.id,
        selected_count=len(candidates),
        summary=comparison["summary"],
        agent_briefing=agent_briefing,
        groups=groups,
        key_differences=comparison["key_differences"],
        recommended_next_actions=comparison["recommended_next_actions"],
        generated_at=datetime.now(timezone.utc),
    )
