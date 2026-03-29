from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


UNKNOWN = "unknown"


class ListingInfo(BaseModel):
    monthly_rent: str = UNKNOWN
    deposit: str = UNKNOWN
    agent_fee: str = UNKNOWN
    management_fee_included: str = UNKNOWN
    rates_included: str = UNKNOWN  # 差饷是否包含
    lease_term: str = UNKNOWN
    move_in_date: str = UNKNOWN
    furnished: str = UNKNOWN
    repair_responsibility: str = UNKNOWN


class RiskItem(BaseModel):
    level: str = Field(description="high | medium | low")
    title: str
    description: str
    source: str = Field(default="rule", description="rule | llm")


class AnalysisResult(BaseModel):
    listing_info: ListingInfo
    missing_fields: List[str]
    risks: List[RiskItem]
    suggested_questions: List[str]
    combined_text: str
    ocr_texts: List[str]
    match_score: Optional[float] = None


class UserPreference(BaseModel):
    """用户偏好设置"""
    user_id: str
    max_budget: Optional[float] = None
    preferred_areas: List[str] = Field(default_factory=list)
    max_commute_time: Optional[int] = None
    commute_destination: Optional[str] = None
    must_have: List[str] = Field(default_factory=list)
    deal_breakers: List[str] = Field(default_factory=list)


class ListingRecord(BaseModel):
    """房源记录（保存到数据库）"""
    id: Optional[str] = None
    user_id: str
    name: str
    listing_info: ListingInfo
    missing_fields: List[str] = Field(default_factory=list)
    risks: List[RiskItem] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    match_score: Optional[float] = None
    combined_text: Optional[str] = None  # 原始文本（可选）
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class User(BaseModel):
    """用户模型"""
    id: Optional[str] = None
    email: str
    password_hash: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
