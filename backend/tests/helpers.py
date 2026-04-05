from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.db.models import (
    CandidateAssessment,
    CandidateExtractedInfo,
    CandidateListing,
    ClauseAssessment,
    CostAssessment,
    SearchProject,
    User,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="tester@example.com",
        password_hash="hashed-password",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def build_project(user: User) -> SearchProject:
    return SearchProject(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Test Project",
        status="active",
        max_budget=22000,
        preferred_districts=["Wan Chai"],
        must_have=["furnished"],
        deal_breakers=["shared bathroom"],
        move_in_target=date(2026, 5, 1),
        notes=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def build_candidate(
    project: SearchProject,
    *,
    candidate_id: uuid.UUID | None = None,
    name: str = "Candidate A",
    status: str = "needs_info",
    user_decision: str = "undecided",
    next_best_action: str = "verify_cost",
) -> CandidateListing:
    candidate = CandidateListing(
        id=candidate_id or uuid.uuid4(),
        project_id=project.id,
        name=name,
        source_type="manual_text",
        raw_listing_text="Rent 18000, management fee unknown",
        raw_chat_text=None,
        raw_note_text=None,
        combined_text="Rent 18000, management fee unknown",
        status=status,
        processing_stage=None,
        processing_error=None,
        user_decision=user_decision,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    candidate.extracted_info = CandidateExtractedInfo(
        candidate_id=candidate.id,
        monthly_rent="18000",
        management_fee_amount=None,
        management_fee_included=None,
        rates_amount=None,
        rates_included=None,
        deposit="36000",
        agent_fee=None,
        lease_term="2 years",
        move_in_date="2026-05-01",
        repair_responsibility="unknown",
        district="Wan Chai",
        furnished="furnished",
        size_sqft="400",
        bedrooms="1",
        suspected_sdu=None,
        sdu_detection_reason=None,
        ocr_texts=[],
    )
    candidate.cost_assessment = CostAssessment(
        candidate_id=candidate.id,
        known_monthly_cost=18000.0,
        monthly_cost_confidence="low",
        monthly_cost_missing_items=["management_fee_amount", "rates_amount"],
        move_in_cost_known_part=54000.0,
        move_in_cost_confidence="medium",
        cost_risk_flag="hidden_cost_risk",
        summary="Need to confirm additional fees.",
    )
    candidate.clause_assessment = ClauseAssessment(
        candidate_id=candidate.id,
        repair_responsibility_level="unknown",
        lease_term_level="standard",
        move_in_date_level="fit",
        clause_confidence="medium",
        clause_risk_flag="needs_confirmation",
        summary="Repair responsibility still needs confirmation.",
    )
    candidate.candidate_assessment = CandidateAssessment(
        candidate_id=candidate.id,
        potential_value_level="high",
        completeness_level="medium",
        critical_uncertainty_level="high",
        decision_risk_level="medium",
        information_gain_level="high",
        recommendation_confidence="low",
        next_best_action=next_best_action,
        status=status,
        labels=["promising", "cost_unknown"],
        summary="Promising candidate that needs more confirmation.",
    )
    return candidate
