"""Project schemas"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Project list response"""
    projects: List[ProjectResponse]
    total: int
