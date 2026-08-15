"""Investigation API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.database import get_db
from ...db.models import CandidateListing, InvestigationItem, User
from ...schemas.dashboard import InvestigationItemSummary
from ...schemas.investigation import InvestigationItemUpdate, InvestigationResponse
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
    open_items, closed_items = await investigation_service.sync_items(
        db=db,
        project=project,
        generated_items=graph_state["open_items"],
    )
    return InvestigationResponse(
        project_id=project.id,
        current_advice=graph_state["current_advice"],
        priority_candidates=graph_state["priority_candidates"],
        open_items=open_items,
        closed_items=closed_items,
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


@router.patch(
    "/projects/{project_id}/investigation/items/{item_id}",
    response_model=InvestigationItemSummary,
)
async def update_investigation_item(
    project_id: UUID,
    item_id: UUID,
    item_data: InvestigationItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's progress on one investigation item."""
    project = await get_project_for_user(project_id, current_user, db)
    result = await db.execute(
        select(InvestigationItem).where(
            InvestigationItem.id == item_id,
            InvestigationItem.project_id == project.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation item not found",
        )

    update_data = item_data.model_dump(exclude_unset=True)
    if "status" in update_data:
        item.status = update_data["status"]
    if "note" in update_data:
        note = update_data["note"]
        item.note = note.strip() if isinstance(note, str) and note.strip() else None

    await db.flush()
    await db.refresh(item)
    return item
