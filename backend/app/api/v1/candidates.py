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
from ...db.models import (
    CandidateFieldEvidence,
    CandidateFieldFact,
    CandidateListing,
    SearchProject,
    User,
)
from ...schemas.candidate import (
    CandidateContactPlanResponse,
    CandidateFieldActionRequest,
    CandidateListResponse,
    CandidateResponse,
    CandidateUpdate,
)
from ...services.candidate_contact_plan_service import CandidateContactPlanService
from ...services.candidate_analysis_state import has_usable_analysis
from ...services.candidate_import_background_service import CandidateImportBackgroundService
from ...services.candidate_import_service import CandidateImportService, build_combined_text, infer_source_type
from ...services.candidate_analysis_runner import run_candidate_analysis
from ...services.candidate_field_correction_service import (
    CandidateFieldAction,
    CandidateFieldCorrectionError,
    CandidateFieldCorrectionService,
)
from ...services.candidate_field_registry import CANDIDATE_FIELD_BY_KEY
from ...services.candidate_field_serialization_service import serialize_candidate_field_facts
from ...services.candidate_pipeline_service import CandidatePipelineService
from ...services.commute_service import CommuteService
from .auth import get_current_user

router = APIRouter()
pipeline_service = CandidatePipelineService()
commute_service = CommuteService()
candidate_contact_plan_service = CandidateContactPlanService()
candidate_import_service = CandidateImportService()
candidate_import_background_service = CandidateImportBackgroundService(get_session_factory())
candidate_field_correction_service = CandidateFieldCorrectionService()


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
            selectinload(CandidateListing.field_facts)
            .selectinload(CandidateFieldFact.evidence)
            .selectinload(CandidateFieldEvidence.source_asset),
        )
    )


async def _serialize_candidate(
    candidate: CandidateListing,
    project: SearchProject | None = None,
    compute_commute: bool = False,
    db: AsyncSession | None = None,
) -> CandidateResponse:
    response = CandidateResponse.model_validate(candidate).model_copy(
        update={"field_facts": serialize_candidate_field_facts(candidate.field_facts)}
    )
    if not has_usable_analysis(candidate):
        return response.model_copy(
            update={
                "extracted_info": None,
                "cost_assessment": None,
                "clause_assessment": None,
                "candidate_assessment": None,
                "benchmark": None,
                "commute_evidence": None,
                "field_facts": [],
            }
        )

    updates: dict = {"benchmark": None}
    if compute_commute and project is not None:
        updates["commute_evidence"] = await commute_service.build_for_candidate(
            project, candidate, db=db
        )
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
        _candidate_detail_query()
        .where(
            CandidateListing.id == candidate_id,
            CandidateListing.project_id == project.id,
        )
        .execution_options(populate_existing=True)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return project, candidate


async def _apply_candidate_field_actions(
    *,
    db: AsyncSession,
    project: SearchProject,
    candidate: CandidateListing,
    actor_user_id: UUID,
    actions: list[CandidateFieldAction],
) -> None:
    try:
        await candidate_field_correction_service.apply_candidate_actions(
            db,
            project=project,
            candidate=candidate,
            actor_user_id=actor_user_id,
            actions=actions,
            pipeline=pipeline_service,
        )
    except CandidateFieldCorrectionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
        processing_error_code=None,
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
    set_committed_value(candidate, "field_facts", [])

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
        candidates=[
            await _serialize_candidate(candidate, project=project, compute_commute=True, db=db)
            for candidate in candidates
        ],
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
    return await _serialize_candidate(candidate, project=project, compute_commute=True, db=db)


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

    location_updates = {k: v for k, v in update_data.items() if k in location_fields}

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
        analysis_succeeded = await run_candidate_analysis(
            db=db,
            project=project,
            candidate=candidate,
            pipeline=pipeline_service,
        )
        if analysis_succeeded:
            _, candidate = await get_candidate_for_project_user(
                project.id,
                candidate.id,
                current_user,
                db,
            )

    if location_updates and (not should_reassess or analysis_succeeded):
        location_actions = [
            CandidateFieldAction(
                field_key=field_key,
                action=(
                    "mark_unknown"
                    if value is None or (isinstance(value, str) and not value.strip())
                    else "correct"
                ),
                value=(
                    None
                    if value is None or (isinstance(value, str) and not value.strip())
                    else value
                ),
            )
            for field_key, value in location_updates.items()
        ]
        await _apply_candidate_field_actions(
            db=db,
            project=project,
            candidate=candidate,
            actor_user_id=current_user.id,
            actions=location_actions,
        )

    if not should_reassess and not location_updates:
        await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(
        candidate,
        project=project,
        compute_commute=not location_updates,
        db=db,
    )


@router.post("/projects/{project_id}/candidates/{candidate_id}/reassess", response_model=CandidateResponse)
async def reassess_candidate(
    project_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rerun assessments for a candidate."""
    project, candidate = await get_candidate_for_project_user(project_id, candidate_id, current_user, db)
    await run_candidate_analysis(
        db=db,
        project=project,
        candidate=candidate,
        pipeline=pipeline_service,
    )
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True, db=db)


@router.patch(
    "/projects/{project_id}/candidates/{candidate_id}/fields/{field_key}",
    response_model=CandidateResponse,
)
async def update_candidate_field(
    project_id: UUID,
    candidate_id: UUID,
    field_key: str,
    field_data: CandidateFieldActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply one auditable field action and locally recalculate affected results."""
    if field_key not in CANDIDATE_FIELD_BY_KEY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported candidate field: {field_key}",
        )

    project, candidate = await get_candidate_for_project_user(
        project_id,
        candidate_id,
        current_user,
        db,
    )
    await _apply_candidate_field_actions(
        db=db,
        project=project,
        candidate=candidate,
        actor_user_id=current_user.id,
        actions=[
            CandidateFieldAction(
                field_key=field_key,
                action=field_data.action,
                value=field_data.value,
                note=field_data.note,
            )
        ],
    )
    _, candidate = await get_candidate_for_project_user(
        project.id,
        candidate.id,
        current_user,
        db,
    )
    return await _serialize_candidate(candidate, project=project, compute_commute=False, db=db)


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
    if not has_usable_analysis(candidate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate analysis must complete successfully before generating a contact plan.",
        )
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
    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True, db=db)


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
    await db.flush()
    _, candidate = await get_candidate_for_project_user(project.id, candidate.id, current_user, db)
    return await _serialize_candidate(candidate, project=project, compute_commute=True, db=db)


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
