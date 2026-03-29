"""数据库配置模块 - SQLAlchemy ORM"""

import os
from datetime import datetime, timezone, timedelta
from typing import Generator

from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from config import settings

# 香港时区 (UTC+8)
HK_TIMEZONE = timezone(timedelta(hours=8))


def get_hk_now() -> datetime:
    """获取香港当前时间"""
    return datetime.now(HK_TIMEZONE)


def utc_to_hk(dt: datetime) -> datetime:
    """将UTC时间转换为香港时间"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 假设是UTC时间
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(HK_TIMEZONE)


# 数据库URL - 从配置模块读取
DATABASE_URL = settings.DATABASE_URL

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


# ==================== 数据库模型定义 ====================

class UserDB(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=get_hk_now)
    last_login = Column(DateTime, nullable=True)


class UserPreferenceDB(Base):
    """用户偏好表"""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    max_budget = Column(Float, nullable=True)
    preferred_areas = Column(JSON, default=list)  # 存储区域列表
    max_commute_time = Column(Float, nullable=True)  # 分钟
    commute_destination = Column(String, nullable=True)
    must_have = Column(JSON, default=list)  # 必须有的设施
    deal_breakers = Column(JSON, default=list)  # 不可接受的条件
    updated_at = Column(DateTime, default=get_hk_now, onupdate=get_hk_now)


class ListingRecordDB(Base):
    """房源记录表"""
    __tablename__ = "listing_records"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)

    # 房源信息（JSON存储）
    listing_info = Column(JSON, nullable=False)
    missing_fields = Column(JSON, default=list)
    risks = Column(JSON, default=list)
    suggested_questions = Column(JSON, default=list)
    match_score = Column(Float, nullable=True)

    # 原始文本（可选存储）
    combined_text = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_hk_now)
    updated_at = Column(DateTime, default=get_hk_now, onupdate=get_hk_now)


# ==================== 数据库操作函数 ====================

def init_db() -> None:
    """初始化数据库（创建所有表）"""
    import os
    try:
        # Log the database path for SQLite
        if DATABASE_URL.startswith("sqlite"):
            db_path = DATABASE_URL.replace("sqlite:///", "")
            print(f"[Database] Initializing at: {os.path.abspath(db_path)}")

        Base.metadata.create_all(bind=engine)
        print("[Database] Tables created successfully")
    except Exception as e:
        print(f"[Database] Initialization failed: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（生成器，用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """直接获取数据库会话"""
    return SessionLocal()
