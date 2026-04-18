"""Commute evidence schema — derived at response time, not persisted."""

from typing import Optional

from pydantic import BaseModel


class CommuteSegment(BaseModel):
    """One leg of a transit route. ``mode`` is one of: walking, subway, bus,
    minibus, rail, airport_express, taxi."""

    mode: str
    line_name: Optional[str] = None
    from_station: Optional[str] = None
    to_station: Optional[str] = None
    duration_minutes: Optional[int] = None
    distance_meters: Optional[int] = None


class CommuteEvidence(BaseModel):
    """Derived commute evidence returned inline on candidate responses."""

    status: str  # not_configured | insufficient_candidate_location | ready | failed
    estimated_minutes: Optional[int] = None
    mode: Optional[str] = None
    route_summary: Optional[str] = None
    origin_station: Optional[str] = None
    destination_station: Optional[str] = None
    segments: Optional[list[CommuteSegment]] = None
    destination_label: Optional[str] = None
    confidence_note: Optional[str] = None
