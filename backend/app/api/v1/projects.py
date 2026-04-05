"""Projects API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.models import CandidateListing, User, SearchProject
from ...schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
)
from ...services.candidate_pipeline_service import CandidatePipelineService
from .auth import get_current_user

router = APIRouter()
pipeline_service = CandidatePipelineService()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new search project"""
    project = SearchProject(
        user_id=current_user.id,
        title=project_data.title,
        max_budget=project_data.max_budget,
        preferred_districts=project_data.preferred_districts,
        must_have=project_data.must_have,
        deal_breakers=project_data.deal_breakers,
        move_in_target=project_data.move_in_target,
        notes=project_data.notes,
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

    if "max_budget" in update_data and update_data["max_budget"] != previous_budget:
        candidate_result = await db.execute(
            select(CandidateListing).where(
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
