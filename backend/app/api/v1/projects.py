"""Projects API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...db.database import get_db
from ...db.models import CandidateListing, User, SearchProject
from ...integrations.amap.client import AmapClient
from ...schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
)
from ...services.candidate_pipeline_service import CandidatePipelineService
from .auth import get_current_user

router = APIRouter()
pipeline_service = CandidatePipelineService()
_amap_client: AmapClient | None = AmapClient(settings.AMAP_API_KEY) if settings.AMAP_API_KEY else None


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new search project"""
    # Resolve commute destination coordinates if configured
    commute_enabled = bool(project_data.commute_destination_query and project_data.commute_mode)
    dest_lat: float | None = None
    dest_lng: float | None = None
    if commute_enabled and _amap_client and project_data.commute_destination_query:
        coords = await _amap_client.geocode(project_data.commute_destination_query)
        if coords:
            dest_lng, dest_lat = coords

    project = SearchProject(
        user_id=current_user.id,
        title=project_data.title,
        max_budget=project_data.max_budget,
        preferred_districts=project_data.preferred_districts,
        must_have=project_data.must_have,
        deal_breakers=project_data.deal_breakers,
        move_in_target=project_data.move_in_target,
        notes=project_data.notes,
        commute_enabled=commute_enabled,
        commute_destination_label=project_data.commute_destination_label,
        commute_destination_query=project_data.commute_destination_query,
        commute_mode=project_data.commute_mode,
        max_commute_minutes=project_data.max_commute_minutes,
        commute_destination_lat=dest_lat,
        commute_destination_lng=dest_lng,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's projects"""
    # Get total count
    count_result = await db.execute(
        select(func.count()).where(SearchProject.user_id == current_user.id)
    )
    total = count_result.scalar()

    # Get projects
    result = await db.execute(
        select(SearchProject)
        .where(SearchProject.user_id == current_user.id)
        .order_by(SearchProject.updated_at.desc())
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get project by ID"""
    result = await db.execute(
        select(SearchProject).where(
            SearchProject.id == project_id,
            SearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update project"""
    result = await db.execute(
        select(SearchProject).where(
            SearchProject.id == project_id,
            SearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    previous_budget = project.max_budget

    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    # Maintain commute_enabled and re-geocode destination if query changed
    commute_fields = {"commute_destination_query", "commute_mode", "commute_destination_label", "max_commute_minutes"}
    if commute_fields & update_data.keys():
        query = project.commute_destination_query
        mode = project.commute_mode
        project.commute_enabled = bool(query and mode)

        if "commute_destination_query" in update_data:
            project.commute_destination_lat = None
            project.commute_destination_lng = None
            if query and _amap_client:
                coords = await _amap_client.geocode(query)
                if coords:
                    project.commute_destination_lng, project.commute_destination_lat = coords

    if "max_budget" in update_data and update_data["max_budget"] != previous_budget:
        candidate_result = await db.execute(
            select(CandidateListing)
            .options(
                selectinload(CandidateListing.source_assets),
                selectinload(CandidateListing.extracted_info),
                selectinload(CandidateListing.cost_assessment),
                selectinload(CandidateListing.clause_assessment),
                selectinload(CandidateListing.candidate_assessment),
            )
            .where(
                CandidateListing.project_id == project.id,
                CandidateListing.combined_text.is_not(None),
            )
        )
        candidates = candidate_result.scalars().all()
        for candidate in candidates:
            if candidate.processing_stage in {"queued", "running_ocr", "extracting"}:
                continue
            await pipeline_service.assess_candidate(db=db, project=project, candidate=candidate)

    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project owned by the current user."""
    result = await db.execute(
        select(SearchProject).where(
            SearchProject.id == project_id,
            SearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.delete(project)
    await db.flush()
