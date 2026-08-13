"""Investigation API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.database import get_db
from ...db.models import CandidateListing, User
from ...schemas.investigation import InvestigationResponse
from ...services.investigation_service import InvestigationService
from .auth import get_current_user
from .candidates import get_project_for_user

router = APIRouter()
investigation_service = InvestigationService()


def _candidate_query_for_project(project_id: UUID):
    return (
        select(CandidateListing)
        .options(
            selectinload(CandidateListing.extracted_info),
            selectinload(CandidateListing.cost_assessment),
            selectinload(CandidateListing.clause_assessment),
            selectinload(CandidateListing.candidate_assessment),
            selectinload(CandidateListing.field_facts),
        )
        .where(CandidateListing.project_id == project_id)
        .order_by(CandidateListing.updated_at.desc())
    )


@router.post("/projects/{project_id}/investigation/run", response_model=InvestigationResponse)
async def run_investigation(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the current lightweight investigation workflow."""
    project = await get_project_for_user(project_id, current_user, db)
    result = await db.execute(_candidate_query_for_project(project.id))
    candidates = result.scalars().all()
    graph_state = await investigation_service.run(project=project, candidates=candidates)
    return InvestigationResponse(
        project_id=project.id,
        current_advice=graph_state["current_advice"],
        priority_candidates=graph_state["priority_candidates"],
        open_items=graph_state["open_items"],
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/projects/{project_id}/investigation/current", response_model=InvestigationResponse)
async def get_current_investigation(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current derived investigation state."""
    return await run_investigation(project_id=project_id, current_user=current_user, db=db)
