"""Commute evidence schema — derived at response time, not persisted."""

from typing import Optional

from pydantic import BaseModel


class CommuteEvidence(BaseModel):
    """Derived commute evidence returned inline on candidate responses."""

    status: str  # not_configured | insufficient_candidate_location | ready | failed
    estimated_minutes: Optional[int] = None
    mode: Optional[str] = None
    route_summary: Optional[str] = None
    destination_label: Optional[str] = None
    confidence_note: Optional[str] = None
