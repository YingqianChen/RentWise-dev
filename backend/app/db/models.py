"""SQLAlchemy database models for all entities"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, String, Text, Integer,
    func, Index, UUID as PG_UUID
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, utc_now


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID"""
    return uuid.uuid4()


class User(Base):
    """User accounts"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    projects: Mapped[List["SearchProject"]] = relationship(
        "SearchProject", back_populates="user", cascade="all, delete-orphan"
    )


class SearchProject(Base):
    """Search project for organizing rental search"""
    __tablename__ = "search_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active | archived | completed
    max_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preferred_districts: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    must_have: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    deal_breakers: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    move_in_target: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    candidates: Mapped[List["CandidateListing"]] = relationship(
        "CandidateListing", back_populates="project", cascade="all, delete-orphan"
    )
    investigation_items: Mapped[List["InvestigationItem"]] = relationship(
        "InvestigationItem", back_populates="project", cascade="all, delete-orphan"
    )


class CandidateListing(Base):
    """Candidate rental listing"""
    __tablename__ = "candidate_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("search_projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), default="manual_text", nullable=False
    )  # manual_text | chat_log | mixed
    raw_listing_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_chat_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_note_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    combined_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="new", nullable=False
    )  # new | needs_info | follow_up | high_risk_pending | recommended_reject | shortlisted
    processing_stage: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # queued | running_ocr | extracting | completed | failed
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_decision: Mapped[str] = mapped_column(
        String(50), default="undecided", nullable=False
    )  # undecided | shortlisted | rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    project: Mapped["SearchProject"] = relationship("SearchProject", back_populates="candidates")
    extracted_info: Mapped["CandidateExtractedInfo"] = relationship(
        "CandidateExtractedInfo", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    cost_assessment: Mapped["CostAssessment"] = relationship(
        "CostAssessment", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    clause_assessment: Mapped["ClauseAssessment"] = relationship(
        "ClauseAssessment", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    candidate_assessment: Mapped["CandidateAssessment"] = relationship(
        "CandidateAssessment", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    source_assets: Mapped[List["CandidateSourceAsset"]] = relationship(
        "CandidateSourceAsset", back_populates="candidate", cascade="all, delete-orphan"
    )
    investigation_items: Mapped[List["InvestigationItem"]] = relationship(
        "InvestigationItem", back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateSourceAsset(Base):
    """Uploaded source file attached to a candidate."""
    __tablename__ = "candidate_source_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate_listings.id", ondelete="CASCADE"), nullable=False
    )
    storage_provider: Mapped[str] = mapped_column(String(50), default="local", nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ocr_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending | succeeded | failed | skipped
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    candidate: Mapped["CandidateListing"] = relationship("CandidateListing", back_populates="source_assets")


class CandidateExtractedInfo(Base):
    """Extracted information from listing text"""
    __tablename__ = "candidate_extracted_info"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("candidate_listings.id", ondelete="CASCADE"),
        primary_key=True
    )
    monthly_rent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    management_fee_amount: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    management_fee_included: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    rates_amount: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rates_included: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    deposit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_fee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_term: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    move_in_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    repair_responsibility: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    furnished: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_sqft: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bedrooms: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suspected_sdu: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    sdu_detection_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ocr_texts: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    # Relationships
    candidate: Mapped["CandidateListing"] = relationship("CandidateListing", back_populates="extracted_info")


class CostAssessment(Base):
    """Cost assessment for a candidate"""
    __tablename__ = "candidate_cost_assessments"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("candidate_listings.id", ondelete="CASCADE"),
        primary_key=True
    )
    known_monthly_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_cost_confidence: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    monthly_cost_missing_items: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    move_in_cost_known_part: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    move_in_cost_confidence: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    cost_risk_flag: Mapped[str] = mapped_column(
        String(50), default="none", nullable=False
    )  # none | possible_additional_cost | hidden_cost_risk | over_budget
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Relationships
    candidate: Mapped["CandidateListing"] = relationship("CandidateListing", back_populates="cost_assessment")


class ClauseAssessment(Base):
    """Clause assessment for a candidate"""
    __tablename__ = "candidate_clause_assessments"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("candidate_listings.id", ondelete="CASCADE"),
        primary_key=True
    )
    repair_responsibility_level: Mapped[str] = mapped_column(
        String(50), default="unknown", nullable=False
    )  # clear | supported_but_unconfirmed | unclear | tenant_heavy | unknown
    lease_term_level: Mapped[str] = mapped_column(
        String(50), default="unknown", nullable=False
    )  # standard | rigid | unstable | unknown
    move_in_date_level: Mapped[str] = mapped_column(
        String(50), default="unknown", nullable=False
    )  # fit | mismatch | uncertain | unknown
    clause_confidence: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    clause_risk_flag: Mapped[str] = mapped_column(
        String(50), default="none", nullable=False
    )  # none | needs_confirmation | high_risk
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Relationships
    candidate: Mapped["CandidateListing"] = relationship("CandidateListing", back_populates="clause_assessment")


class CandidateAssessment(Base):
    """Overall assessment for a candidate"""
    __tablename__ = "candidate_assessments"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("candidate_listings.id", ondelete="CASCADE"),
        primary_key=True
    )
    potential_value_level: Mapped[str] = mapped_column(
        String(50), default="medium", nullable=False
    )  # high | medium | low
    completeness_level: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    critical_uncertainty_level: Mapped[str] = mapped_column(
        String(50), default="high", nullable=False
    )  # high | medium | low
    decision_risk_level: Mapped[str] = mapped_column(
        String(50), default="high", nullable=False
    )  # high | medium | low
    information_gain_level: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    recommendation_confidence: Mapped[str] = mapped_column(
        String(50), default="low", nullable=False
    )  # high | medium | low
    next_best_action: Mapped[str] = mapped_column(
        String(50), default="verify_cost", nullable=False
    )  # verify_cost | verify_clause | schedule_viewing | keep_warm | reject
    status: Mapped[str] = mapped_column(
        String(50), default="new", nullable=False
    )  # new | needs_info | follow_up | high_risk_pending | recommended_reject | shortlisted
    labels: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Relationships
    candidate: Mapped["CandidateListing"] = relationship("CandidateListing", back_populates="candidate_assessment")

    @property
    def top_level_recommendation(self) -> str:
        """High-level recommendation derived from the current assessment state."""
        if self.next_best_action == "reject" or self.status == "recommended_reject":
            return "likely_reject"
        if self.next_best_action == "schedule_viewing" and self.recommendation_confidence in {"high", "medium"}:
            return "shortlist_recommendation"
        return "not_ready"


class InvestigationItem(Base):
    """Investigation item for a project or candidate"""
    __tablename__ = "investigation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("search_projects.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate_listings.id", ondelete="CASCADE"), nullable=True
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # cost | clause | timing | match
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(50), default="medium", nullable=False
    )  # high | medium | low
    status: Mapped[str] = mapped_column(
        String(50), default="open", nullable=False
    )  # open | resolved | dismissed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    project: Mapped["SearchProject"] = relationship("SearchProject", back_populates="investigation_items")
    candidate: Mapped[Optional["CandidateListing"]] = relationship(
        "CandidateListing", back_populates="investigation_items"
    )


# Indexes for common queries
Index("ix_search_projects_user_id", SearchProject.user_id)
Index("ix_search_projects_status", SearchProject.status)
Index("ix_candidate_listings_project_id", CandidateListing.project_id)
Index("ix_candidate_listings_status", CandidateListing.status)
Index("ix_candidate_listings_user_decision", CandidateListing.user_decision)
Index("ix_candidate_source_assets_candidate_id", CandidateSourceAsset.candidate_id)
Index("ix_investigation_items_project_id", InvestigationItem.project_id)
Index("ix_investigation_items_candidate_id", InvestigationItem.candidate_id)
Index("ix_investigation_items_status", InvestigationItem.status)
