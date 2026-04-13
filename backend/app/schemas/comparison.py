"""Comparison schemas for shortlist decision workspace."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .benchmark import BenchmarkEvidence
from .commute import CommuteEvidence

class ComparisonRequest(BaseModel):
    """Request payload for comparing a selected candidate set."""

    candidate_ids: List[UUID] = Field(min_length=2)


class CompareSummary(BaseModel):
    """High-level summary of the current comparison state."""

    headline: str
    summary: str
    confidence_note: str


class CompareAgentBriefing(BaseModel):
    """LLM-assisted top-level briefing for the compare workspace."""

    current_take: str
    why_now: str
    what_could_change: str
    today_s_move: str
    confidence_note: str


class CompareCandidateCard(BaseModel):
    """Decision-oriented candidate card shown in compare groups."""

    candidate_id: UUID
    name: str
    compare_group: str
    top_recommendation: str
    decision_explanation: str
    main_tradeoff: str
    open_blocker: Optional[str]
    next_action: str
    monthly_rent: Optional[str]
    district: Optional[str]
    status: str
    benchmark: Optional[BenchmarkEvidence] = None
    commute_evidence: Optional[CommuteEvidence] = None


class CompareDecisionGroups(BaseModel):
    """Grouped comparison result."""

    best_current_option: Optional[CompareCandidateCard]
    viable_alternatives: List[CompareCandidateCard]
    not_ready_for_fair_comparison: List[CompareCandidateCard]
    likely_drop: List[CompareCandidateCard]


class CompareDifference(BaseModel):
    """Cross-candidate difference worth surfacing to the user."""

    category: str
    title: str
    summary: str


class CompareActionTarget(BaseModel):
    """Single target candidate for a recommended action."""

    candidate_id: UUID
    name: str
    reason: str


class CompareRecommendedActions(BaseModel):
    """Action-oriented next steps derived from the compare set."""

    contact_first: Optional[CompareActionTarget]
    questions_to_ask: List[str]
    viewing_candidate: Optional[CompareActionTarget]
    deprioritize: List[CompareActionTarget]


class SuggestedComparePreview(BaseModel):
    """Lightweight compare preview used on dashboard surfaces."""

    candidate_ids: List[UUID]
    candidate_names: List[str]
    headline: str
    summary: str
    action_prompt: str


class ComparisonResponse(BaseModel):
    """Full comparison response for the shortlist decision workspace."""

    project_id: UUID
    selected_count: int
    summary: CompareSummary
    agent_briefing: CompareAgentBriefing
    groups: CompareDecisionGroups
    key_differences: List[CompareDifference]
    recommended_next_actions: CompareRecommendedActions
    generated_at: datetime
