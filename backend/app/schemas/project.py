"""Project schemas"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_DEPARTURE_WINDOW_PATTERN = "^(now|peak_morning|peak_evening|peak_both|custom)$"
_HHMM_PATTERN = "^([01]\\d|2[0-3]):[0-5]\\d$"


def _normalize_preference_list(value: object) -> list[str]:
    """Keep free-form project preferences short, clean, and deterministic."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Preference lists must be arrays of text values.")

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Preference lists must contain text values.")
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)

    if len(result) > 20:
        raise ValueError("Each preference list can contain at most 20 items.")
    return result


class ProjectCreate(BaseModel):
    """Create project request"""
    title: str = Field(..., min_length=1, max_length=255)
    max_budget: Optional[int] = Field(None, ge=0)
    preferred_districts: List[str] = Field(default_factory=list)
    must_have: List[str] = Field(default_factory=list)
    deal_breakers: List[str] = Field(default_factory=list)
    move_in_target: Optional[date] = None
    notes: Optional[str] = None
    # Commute configuration
    commute_destination_label: Optional[str] = None
    commute_destination_query: Optional[str] = None
    commute_mode: Optional[str] = Field(None, pattern="^(transit|driving|walking)$")
    max_commute_minutes: Optional[int] = Field(None, ge=1, le=180)
    commute_departure_window: Optional[str] = Field(None, pattern=_DEPARTURE_WINDOW_PATTERN)
    commute_departure_time: Optional[str] = Field(None, pattern=_HHMM_PATTERN)

    _clean_preference_lists = field_validator(
        "preferred_districts", "must_have", "deal_breakers", mode="before"
    )(_normalize_preference_list)


class ProjectUpdate(BaseModel):
    """Update project request"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern="^(active|archived|completed)$")
    max_budget: Optional[int] = Field(None, ge=0)
    preferred_districts: Optional[List[str]] = None
    must_have: Optional[List[str]] = None
    deal_breakers: Optional[List[str]] = None
    move_in_target: Optional[date] = None
    notes: Optional[str] = None
    # Commute configuration
    commute_destination_label: Optional[str] = None
    commute_destination_query: Optional[str] = None
    commute_mode: Optional[str] = Field(None, pattern="^(transit|driving|walking)$")
    max_commute_minutes: Optional[int] = Field(None, ge=1, le=180)
    commute_departure_window: Optional[str] = Field(None, pattern=_DEPARTURE_WINDOW_PATTERN)
    commute_departure_time: Optional[str] = Field(None, pattern=_HHMM_PATTERN)

    _clean_preference_lists = field_validator(
        "preferred_districts", "must_have", "deal_breakers", mode="before"
    )(_normalize_preference_list)


class ProjectResponse(BaseModel):
    """Project response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    status: str
    max_budget: Optional[int]
    preferred_districts: List[str]
    must_have: List[str]
    deal_breakers: List[str]
    move_in_target: Optional[date]
    notes: Optional[str]
    commute_enabled: bool = False
    commute_destination_label: Optional[str] = None
    commute_destination_query: Optional[str] = None
    commute_mode: Optional[str] = None
    max_commute_minutes: Optional[int] = None
    commute_destination_lat: Optional[float] = None
    commute_destination_lng: Optional[float] = None
    commute_departure_window: str = "peak_both"
    commute_departure_time: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Project list response"""
    projects: List[ProjectResponse]
    total: int
