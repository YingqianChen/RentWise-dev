"""配置管理模块 - 使用 pydantic-settings 统一管理配置

配置加载顺序：
1. 环境变量
2. .env 文件

启动验证：
- SECRET_KEY 必须存在且至少16字符
- DATABASE_URL 格式验证
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 认证配置 (必须设置)
    SECRET_KEY: str

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./rentwise.db"

    # LLM 服务配置
    LLM_PROVIDER: str = "groq"  # "ollama" 或 "groq"
    OLLAMA_HOST: str = "localhost"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "llama3.3:is6620"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # 地图 API 配置 (OpenRouteService)
    MAPS_API_KEY: Optional[str] = None

    # 应用配置
    APP_ENV: str = "development"  # development | production

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """验证 SECRET_KEY 安全性"""
        if not v:
            raise ValueError("SECRET_KEY 必须设置，请在 .env 文件中配置")
        if len(v) < 16:
            raise ValueError("SECRET_KEY 必须至少16个字符，当前长度: {}".format(len(v)))
        if v == "dev-secret-key-change-in-production":
            raise ValueError("SECRET_KEY 不能使用默认值，请生成新的密钥")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """验证数据库URL格式"""
        if not v:
            return "sqlite:///./rentwise.db"
        if not v.startswith(("sqlite://", "postgresql://", "mysql://")):
            raise ValueError("DATABASE_URL 格式不正确，支持: sqlite://, postgresql://, mysql://")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略多余的环境变量


# 全局配置实例（模块加载时验证配置）
try:
    settings = Settings()
except Exception as e:
    print(f"\n{'='*60}")
    print(f"配置错误: {e}")
    print(f"{'='*60}")
    print("\n请确保 .env 文件存在并包含必要配置:")
    print("  SECRET_KEY=your-secret-key-at-least-16-characters")
    print("  DATABASE_URL=sqlite:///./rentwise.db")
    print("\n可以复制 .env.example 为 .env 并修改配置值")
    print(f"{'='*60}\n")
    raise
