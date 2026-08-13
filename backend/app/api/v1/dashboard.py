"""Dashboard API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.database import get_db
from ...db.models import CandidateListing, User
from ...schemas.dashboard import DashboardResponse
from ...services.comparison_service import ComparisonService
from ...services.investigation_service import InvestigationService
from .auth import get_current_user
from .candidates import get_project_for_user

router = APIRouter()
investigation_service = InvestigationService()
comparison_service = ComparisonService()


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


@router.get("/projects/{project_id}/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a live dashboard summary for the project."""
    project = await get_project_for_user(project_id, current_user, db)
    result = await db.execute(_candidate_query_for_project(project.id))
    candidates = result.scalars().all()

    graph_state = await investigation_service.run(project=project, candidates=candidates)
    return DashboardResponse(
        project_id=project.id,
        stats=graph_state["stats"],
        current_advice=graph_state["current_advice"],
        priority_candidates=graph_state["priority_candidates"],
        open_investigation_items=graph_state["open_items"],
        compare_preview=comparison_service.build_compare_preview(project=project, candidates=candidates),
        generated_at=datetime.now(timezone.utc),
    )
