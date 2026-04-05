"""Candidate schemas"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .benchmark import BenchmarkEvidence

# ============== Extracted Info ==============

class ExtractedInfoResponse(BaseModel):
    """Extracted info response"""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: UUID
    monthly_rent: Optional[str]
    management_fee_amount: Optional[str]
    management_fee_included: Optional[bool]
    rates_amount: Optional[str]
    rates_included: Optional[bool]
    deposit: Optional[str]
    agent_fee: Optional[str]
    lease_term: Optional[str]
    move_in_date: Optional[str]
    repair_responsibility: Optional[str]
    district: Optional[str]
    furnished: Optional[str]
    size_sqft: Optional[str]
    bedrooms: Optional[str]
    suspected_sdu: Optional[bool]
    sdu_detection_reason: Optional[str]
    ocr_texts: List[str]


class CandidateSourceAssetResponse(BaseModel):
    """Uploaded candidate source asset"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    storage_provider: str
    storage_key: str
    original_filename: str
    content_type: Optional[str]
    file_size: Optional[int]
    ocr_status: str
    ocr_text: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============== Assessments ==============

class CostAssessmentResponse(BaseModel):
    """Cost assessment response"""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: UUID
    known_monthly_cost: Optional[float]
    monthly_cost_confidence: str
    monthly_cost_missing_items: List[str]
    move_in_cost_known_part: Optional[float]
    move_in_cost_confidence: str
    cost_risk_flag: str
    summary: str


class ClauseAssessmentResponse(BaseModel):
    """Clause assessment response"""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: UUID
    repair_responsibility_level: str
    lease_term_level: str
    move_in_date_level: str
    clause_confidence: str
    clause_risk_flag: str
    summary: str


class CandidateAssessmentResponse(BaseModel):
    """Candidate assessment response"""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: UUID
    top_level_recommendation: str
    potential_value_level: str
    completeness_level: str
    critical_uncertainty_level: str
    decision_risk_level: str
    information_gain_level: str
    recommendation_confidence: str
    next_best_action: str
    status: str
    labels: List[str]
    summary: str


# ============== Candidate ==============

class CandidateImport(BaseModel):
    """Import candidate request"""
    name: Optional[str] = Field(None, max_length=255)
    source_type: Optional[str] = Field(default=None, pattern="^(manual_text|chat_log|image_upload|mixed)$")
    raw_listing_text: Optional[str] = None
    raw_chat_text: Optional[str] = None
    raw_note_text: Optional[str] = None


class CandidateUpdate(BaseModel):
    """Update candidate request"""
    name: Optional[str] = Field(None, max_length=255)
    raw_listing_text: Optional[str] = None
    raw_chat_text: Optional[str] = None
    raw_note_text: Optional[str] = None


class CandidateContactPlanResponse(BaseModel):
    """LLM-assisted outreach plan for the next landlord/agent message."""

    contact_goal: str
    questions: List[str]
    message_draft: str


class CandidateResponse(BaseModel):
    """Candidate response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    source_type: str
    raw_listing_text: Optional[str]
    raw_chat_text: Optional[str]
    raw_note_text: Optional[str]
    combined_text: Optional[str]
    status: str
    processing_stage: Optional[str]
    processing_error: Optional[str]
    user_decision: str
    created_at: datetime
    updated_at: datetime
    extracted_info: Optional[ExtractedInfoResponse] = None
    cost_assessment: Optional[CostAssessmentResponse] = None
    clause_assessment: Optional[ClauseAssessmentResponse] = None
    candidate_assessment: Optional[CandidateAssessmentResponse] = None
    benchmark: Optional[BenchmarkEvidence] = None
    source_assets: List[CandidateSourceAssetResponse] = Field(default_factory=list)


class CandidateListResponse(BaseModel):
    """Candidate list response"""
    candidates: List[CandidateResponse]
    total: int


class CandidateSummary(BaseModel):
    """Candidate summary for dashboard"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    user_decision: str
    potential_value_level: str
    completeness_level: str
    next_best_action: str
    monthly_rent: Optional[str]
    district: Optional[str]
