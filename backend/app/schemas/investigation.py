"""Investigation schemas"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .dashboard import InvestigationItemSummary, PriorityCandidate


class InvestigationState(BaseModel):
    """Investigation state for LangGraph"""
    project_id: str
    candidate_ids: List[str]
    candidates: List[dict]
    candidate_assessments: List[dict]
    priority_candidates: List[dict]
    open_items: List[dict]
    current_advice: str


class InvestigationResponse(BaseModel):
    """Investigation run response"""
    project_id: UUID
    current_advice: str
    priority_candidates: List[PriorityCandidate]
    open_items: List[InvestigationItemSummary]
    closed_items: List[InvestigationItemSummary] = Field(default_factory=list)
    generated_at: datetime


class InvestigationItemUpdate(BaseModel):
    """User-controlled status and note for an investigation item."""

    status: Optional[Literal["open", "resolved", "dismissed"]] = None
    note: Optional[str] = Field(default=None, max_length=2000)
