"""Candidates API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.params import Form as FormParam
from fastapi.params import File as FileParam
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import selectinload

from ...db.database import get_db, get_session_factory
from ...db.models import CandidateListing, SearchProject, User
from ...schemas.candidate import (
    CandidateContactPlanResponse,
    CandidateListResponse,
    CandidateResponse,
    CandidateUpdate,
)
from ...services.benchmark_service import BenchmarkService
from ...services.candidate_contact_plan_service import CandidateContactPlanService
from ...services.candidate_import_background_service import CandidateImportBackgroundService
from ...services.candidate_import_service import CandidateImportService, build_combined_text, infer_source_type
from ...services.candidate_pipeline_service import CandidatePipelineService
from ...services.commute_service import CommuteService
from .auth import get_current_user

router = APIRouter()
pipeline_service = CandidatePipelineService()
benchmark_service = BenchmarkService()
commute_service = CommuteService()
candidate_contact_plan_service = CandidateContactPlanService()
candidate_import_service = CandidateImportService()
candidate_import_background_service = CandidateImportBackgroundService(get_session_factory())


async def get_project_for_user(project_id: UUID, user: User, db: AsyncSession) -> SearchProject:
    """Get a project owned by the current user."""
    result = await db.execute(
        select(SearchProject).where(
            SearchProject.id == project_id,
            SearchProject.user_id == user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _candidate_detail_query():
    return (
        select(CandidateListing)
        .options(
            selectinload(CandidateListing.extracted_info),
            selectinload(CandidateListing.cost_assessment),
            selectinload(CandidateListing.clause_assessment),
            selectinload(CandidateListing.candidate_assessment),
            selectinload(CandidateListing.source_assets),
        )
    )


async def _serialize_candidate(
    candidate: CandidateListing,
    project: SearchProject | None = None,
    compute_commute: bool = False,
) -> CandidateResponse:
    response = CandidateResponse.model_validate(candidate)
    updates: dict = {"benchmark": benchmark_service.build_for_candidate(candidate)}
    if compute_commute and project is not None:
        updates["commute_evidence"] = await commute_service.build_for_candidate(project, candidate)
    return response.model_copy(update=updates)


def _coerce_optional_text(value: str | None) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, FormParam):
        return None
    return value


def _coerce_uploaded_images(value: list[UploadFile] | None) -> list[UploadFile]:
    if isinstance(value, FileParam) or value is None:
        return []
    return value


async def get_candidate_for_project_user(
    project_id: UUID,
    candidate_id: UUID,
    user: User,
    db: AsyncSession,
) -> tuple[SearchProject, CandidateListing]:
    """Get a candidate belonging to a project owned by the current user."""
    project = await get_project_for_user(project_id, user, db)
    result = await db.execute(
        _candidate_detail_query().where(
            CandidateListing.id == candidate_id,
            CandidateListing.project_id == project.id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return project, candidate


@router.post("/projects/{project_id}/candidates/import", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def import_candidate(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    name: str | None = Form(default=None),
    source_type: str | None = Form(default=None),
    raw_listing_text: str | None = Form(default=None),
    raw_chat_text: str | None = Form(default=None),
    raw_note_text: str | None = Form(default=None),
    uploaded_images: list[UploadFile] | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import a new candidate listing and queue OCR/assessment in the background."""
    project = await get_project_for_user(project_id, current_user, db)
    name = _coerce_optional_text(name)
    source_type = _coerce_optional_text(source_type)
    raw_listing_text = _coerce_optional_text(raw_listing_text)
    raw_chat_text = _coerce_optional_text(raw_chat_text)
    raw_note_text = _coerce_optional_text(raw_note_text)
    uploaded_images = _coerce_uploaded_images(uploaded_images)

    inferred_source_type = infer_source_type(
        source_type=source_type,
        has_listing_text=bool(raw_listing_text and raw_listing_text.strip()),
        has_chat_text=bool(raw_chat_text and raw_chat_text.strip()),
        has_note_text=bool(raw_note_text and raw_note_text.strip()),
        has_images=bool(uploaded_images),
    )

    candidate_name = name
    should_autoname = not candidate_name
    if not candidate_name:
        count_result = await db.execute(select(func.count()).where(CandidateListing.project_id == project.id))
        candidate_name = f"Candidate {int(count_result.scalar() or 0) + 1}"

    candidate = CandidateListing(
        project_id=project.id,
        name=candidate_name,
        source_type=inferred_source_type,
        raw_listing_text=raw_listing_text,
        raw_chat_text=raw_chat_text,
        raw_note_text=raw_note_text,
        combined_text=build_combined_text(raw_listing_text, raw_chat_text, raw_note_text),
        processing_stage="queued",
        processing_error=None,
    )
    db.add(candidate)
    await db.flush()

    source_assets = await candidate_import_service.prepare_uploaded_images(
        candidate=candidate,
        uploaded_images=uploaded_images,
    )
    if source_assets:
        db.add_all(source_assets)
    set_committed_value(candidate, "source_assets", source_assets)
    set_committed_value(candidate, "extracted_info", None)
    set_committed_value(candidate, "cost_assessment", None)
    set_committed_value(candidate, "clause_assessment", None)
    set_committed_value(candidate, "candidate_assessment", None)

    if not candidate.combined_text:
        if not uploaded_images:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please provide text or upload at least one image.")
        candidate.processing_error = "Waiting for OCR to read the uploaded images."

    await db.flush()
    await db.commit()
    background_tasks.add_task(
        candidate_import_background_service.process_candidate_import,
        project_id=project.id,
        candidate_id=candidate.id,
        should_autoname=should_autoname,
    )
    return await _serialize_candidate(candidate)


@router.get("/projects/{project_id}/candidates", response_model=CandidateListResponse)
async def list_candidates(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List candidates for a project."""
    project = await get_project_for_user(project_id, current_user, db)
    count_result = await db.execute(select(func.count()).where(CandidateListing.project_id == project.id))
    total = count_result.scalar() or 0

    result = await db.execute(
        _candidate_detail_query()
        .where(CandidateListing.project_id == project.id)
        .order_by(CandidateListing.updated_at.desc())
    )
    candidates = result.scalars().all()
    return CandidateListResponse(
        candidates=[await _serialize_candidate(candidate) for candidate in candidates],
        total=total,
    )


@router.get("/projects/{project_id}/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a candidate by ID."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True)


@router.put("/projects/{project_id}/candidates/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    project_id: UUID,
    candidate_id: UUID,
    candidate_data: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update candidate content and rerun assessments when text changes."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)

    update_data = candidate_data.model_dump(exclude_unset=True)
    text_fields = {"raw_listing_text", "raw_chat_text", "raw_note_text"}
    location_fields = {"address_text", "building_name", "nearest_station"}
    should_reassess = any(field in update_data for field in text_fields)

    # Apply location field updates to extracted_info
    location_updates = {k: v for k, v in update_data.items() if k in location_fields}
    if location_updates and candidate.extracted_info is not None:
        for field, value in location_updates.items():
            setattr(candidate.extracted_info, field, value)
        candidate.extracted_info.location_source = "user_corrected"

    # Apply non-location fields to candidate
    for field, value in update_data.items():
        if field not in location_fields:
            setattr(candidate, field, value)

    if should_reassess:
        candidate.combined_text = "\n".join(
            part.strip()
            for part in [
                candidate.raw_listing_text or "",
                candidate.raw_chat_text or "",
                candidate.raw_note_text or "",
            ]
            if part and part.strip()
        ) or None
        if not candidate.combined_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one text field is required",
            )
        await pipeline_service.assess_candidate(db=db, project=project, candidate=candidate)

    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True)


@router.post("/projects/{project_id}/candidates/{candidate_id}/reassess", response_model=CandidateResponse)
async def reassess_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rerun assessments for a candidate."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    await pipeline_service.assess_candidate(db=db, project=project, candidate=candidate)
    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True)


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/contact-plan",
    response_model=CandidateContactPlanResponse,
)
async def generate_candidate_contact_plan(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a short outreach plan for the next landlord/agent message."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    return await candidate_contact_plan_service.build(project=project, candidate=candidate)


@router.post("/projects/{project_id}/candidates/{candidate_id}/shortlist", response_model=CandidateResponse)
async def shortlist_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Shortlist a candidate."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    candidate.user_decision = "shortlisted"
    candidate.status = "shortlisted"
    if candidate.candidate_assessment is not None:
        candidate.candidate_assessment.status = "shortlisted"
    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True)


@router.post("/projects/{project_id}/candidates/{candidate_id}/reject", response_model=CandidateResponse)
async def reject_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a candidate."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    candidate.user_decision = "rejected"
    candidate.status = "recommended_reject"
    if candidate.candidate_assessment is not None:
        candidate.candidate_assessment.status = "recommended_reject"
    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True)


@router.delete("/projects/{project_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a candidate from a project owned by the current user."""
    _, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    await db.delete(candidate)
    await db.flush()
