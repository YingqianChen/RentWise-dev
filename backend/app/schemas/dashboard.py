"""Dashboard schemas"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .comparison import SuggestedComparePreview


class CandidateStats(BaseModel):
    """Candidate statistics"""
    total: int
    new: int
    needs_info: int
    follow_up: int
    high_risk_pending: int
    recommended_reject: int
    shortlisted: int
    rejected: int
    processing: int = 0
    analysis_failed: int = 0


class PriorityCandidate(BaseModel):
    """Priority candidate for dashboard"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    potential_value_level: str
    completeness_level: str
    next_best_action: str
    monthly_rent: Optional[str]
    district: Optional[str]
    reason: str
    priority_score: float


class InvestigationItemSummary(BaseModel):
    """Investigation item summary for dashboard"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: Optional[UUID]
    category: str
    title: str
    question: str
    priority: str
    status: str
    note: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard response"""
    project_id: UUID
    stats: CandidateStats
    current_advice: str
    priority_candidates: List[PriorityCandidate]
    open_investigation_items: List[InvestigationItemSummary]
    closed_investigation_items: List[InvestigationItemSummary] = Field(default_factory=list)
    compare_preview: Optional[SuggestedComparePreview] = None
    generated_at: datetime
