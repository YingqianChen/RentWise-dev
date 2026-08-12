"""Investigation schemas"""

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel

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
    generated_at: datetime
