"""数据访问层 - Repository Pattern"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from database import UserDB, UserPreferenceDB, ListingRecordDB, get_db_session, get_hk_now
from models import User, UserPreference, ListingRecord, ListingInfo, RiskItem


# ==================== 用户 Repository ====================

class UserRepository:
    """用户数据访问"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or get_db_session()

    def create_user(self, email: str, password_hash: str) -> User:
        """创建新用户"""
        user_id = str(uuid.uuid4())
        db_user = UserDB(
            id=user_id,
            email=email,
            password_hash=password_hash,
            created_at=get_hk_now()
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return self._to_model(db_user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        db_user = self.db.query(UserDB).filter(UserDB.email == email).first()
        return self._to_model(db_user) if db_user else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        db_user = self.db.query(UserDB).filter(UserDB.id == user_id).first()
        return self._to_model(db_user) if db_user else None

    def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        user = self.db.query(UserDB).filter(UserDB.id == user_id).first()
        if user:
            user.last_login = get_hk_now()
            self.db.commit()

    def _to_model(self, db_user: UserDB) -> User:
        """转换为Pydantic模型"""
        return User(
            id=db_user.id,
            email=db_user.email,
            password_hash=db_user.password_hash,
            created_at=db_user.created_at,
            last_login=db_user.last_login
        )


# ==================== 用户偏好 Repository ====================

class PreferenceRepository:
    """用户偏好数据访问"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or get_db_session()

    def get_preference(self, user_id: str) -> Optional[UserPreference]:
        """获取用户偏好"""
        db_pref = self.db.query(UserPreferenceDB).filter(
            UserPreferenceDB.user_id == user_id
        ).first()
        return self._to_model(db_pref) if db_pref else None

    def save_preference(self, preference: UserPreference) -> UserPreference:
        """保存或更新用户偏好"""
        existing = self.db.query(UserPreferenceDB).filter(
            UserPreferenceDB.user_id == preference.user_id
        ).first()

        if existing:
            # 更新
            existing.max_budget = preference.max_budget
            existing.preferred_areas = preference.preferred_areas
            existing.max_commute_time = preference.max_commute_time
            existing.commute_destination = preference.commute_destination
            existing.must_have = preference.must_have
            existing.deal_breakers = preference.deal_breakers
            existing.updated_at = get_hk_now()
        else:
            # 新建
            db_pref = UserPreferenceDB(
                id=str(uuid.uuid4()),
                user_id=preference.user_id,
                max_budget=preference.max_budget,
                preferred_areas=preference.preferred_areas,
                max_commute_time=preference.max_commute_time,
                commute_destination=preference.commute_destination,
                must_have=preference.must_have,
                deal_breakers=preference.deal_breakers
            )
            self.db.add(db_pref)

        self.db.commit()
        return preference

    def _to_model(self, db_pref: UserPreferenceDB) -> UserPreference:
        """转换为Pydantic模型"""
        return UserPreference(
            user_id=db_pref.user_id,
            max_budget=db_pref.max_budget,
            preferred_areas=db_pref.preferred_areas or [],
            max_commute_time=int(db_pref.max_commute_time) if db_pref.max_commute_time else None,
            commute_destination=db_pref.commute_destination,
            must_have=db_pref.must_have or [],
            deal_breakers=db_pref.deal_breakers or []
        )


# ==================== 房源记录 Repository ====================

class ListingRepository:
    """房源记录数据访问"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or get_db_session()

    def create_listing(self, record: ListingRecord) -> ListingRecord:
        """创建房源记录"""
        record_id = str(uuid.uuid4())
        db_record = ListingRecordDB(
            id=record_id,
            user_id=record.user_id,
            name=record.name,
            listing_info=record.listing_info.model_dump(),
            missing_fields=record.missing_fields,
            risks=[r.model_dump() for r in record.risks],
            suggested_questions=record.suggested_questions,
            match_score=record.match_score,
            combined_text=record.combined_text,
            created_at=get_hk_now(),
            updated_at=get_hk_now()
        )
        self.db.add(db_record)
        self.db.commit()
        self.db.refresh(db_record)
        return self._to_model(db_record)

    def get_listing(self, listing_id: str, user_id: str) -> Optional[ListingRecord]:
        """获取单个房源（带用户验证）"""
        db_record = self.db.query(ListingRecordDB).filter(
            ListingRecordDB.id == listing_id,
            ListingRecordDB.user_id == user_id
        ).first()
        return self._to_model(db_record) if db_record else None

    def get_user_listings(self, user_id: str) -> List[ListingRecord]:
        """获取用户的所有房源"""
        db_records = self.db.query(ListingRecordDB).filter(
            ListingRecordDB.user_id == user_id
        ).order_by(ListingRecordDB.updated_at.desc()).all()
        return [self._to_model(r) for r in db_records]

    def update_listing(self, record: ListingRecord) -> Optional[ListingRecord]:
        """更新房源记录"""
        db_record = self.db.query(ListingRecordDB).filter(
            ListingRecordDB.id == record.id,
            ListingRecordDB.user_id == record.user_id
        ).first()

        if not db_record:
            return None

        db_record.name = record.name
        db_record.listing_info = record.listing_info.model_dump()
        db_record.missing_fields = record.missing_fields
        db_record.risks = [r.model_dump() for r in record.risks]
        db_record.suggested_questions = record.suggested_questions
        db_record.match_score = record.match_score
        db_record.updated_at = get_hk_now()

        self.db.commit()
        self.db.refresh(db_record)
        return self._to_model(db_record)

    def delete_listing(self, listing_id: str, user_id: str) -> bool:
        """删除房源记录"""
        db_record = self.db.query(ListingRecordDB).filter(
            ListingRecordDB.id == listing_id,
            ListingRecordDB.user_id == user_id
        ).first()

        if db_record:
            self.db.delete(db_record)
            self.db.commit()
            return True
        return False

    def _to_model(self, db_record: ListingRecordDB) -> ListingRecord:
        """转换为Pydantic模型"""
        return ListingRecord(
            id=db_record.id,
            user_id=db_record.user_id,
            name=db_record.name,
            listing_info=ListingInfo(**db_record.listing_info),
            missing_fields=db_record.missing_fields or [],
            risks=[RiskItem(**r) for r in (db_record.risks or [])],
            suggested_questions=db_record.suggested_questions or [],
            match_score=db_record.match_score,
            combined_text=db_record.combined_text,
            created_at=db_record.created_at,
            updated_at=db_record.updated_at
        )
