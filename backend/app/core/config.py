"""Configuration management using pydantic-settings."""

from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration"""

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parents[2] / ".env"),
            str(Path(__file__).resolve().parents[3] / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Authentication (required)
    SECRET_KEY: str

    # Database
    DATABASE_URL: str

    # LLM Service Configuration
    LLM_PROVIDER: str = "groq"  # "ollama" or "groq"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "llama3.3"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Application
    APP_ENV: str = "development"  # development | production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    FILE_STORAGE_PROVIDER: str = "local"
    LOCAL_UPLOAD_ROOT: str = str(Path(__file__).resolve().parents[2] / "storage")
    OCR_PROVIDER: str = "rapidocr"
    PADDLEOCR_LANG: str = "ch"
    OCR_USE_DOC_ORIENTATION: bool = False
    OCR_USE_DOC_UNWARPING: bool = False
    OCR_USE_TEXTLINE_ORIENTATION: bool = False
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK: bool = True
    OCR_PREWARM_ON_STARTUP: bool = True
    OCR_MAX_IMAGE_DIMENSION: int = 1600

    @field_validator("OCR_PROVIDER")
    @classmethod
    def validate_ocr_provider(cls, v: str) -> str:
        """Validate supported OCR backends."""
        normalized = v.strip().lower()
        if normalized not in {"rapidocr", "paddleocr"}:
            raise ValueError("OCR_PROVIDER must be `rapidocr` or `paddleocr`")
        return normalized

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any) -> list[str]:
        """Accept comma-separated or list-based CORS origins."""
        default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if v is None:
            return default_origins
        if isinstance(v, str):
            parsed = [origin.strip() for origin in v.split(",") if origin.strip()]
            return parsed or default_origins
        if isinstance(v, (list, tuple, set)):
            parsed = [str(origin).strip() for origin in v if str(origin).strip()]
            return parsed or default_origins
        raise ValueError("BACKEND_CORS_ORIGINS must be a comma-separated string or list")

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY security"""
        if not v:
            raise ValueError("SECRET_KEY must be set in .env file")
        if len(v) < 16:
            raise ValueError(f"SECRET_KEY must be at least 16 characters, got {len(v)}")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format"""
        if not v:
            raise ValueError("DATABASE_URL must be set in .env file")
        valid_prefixes = ("postgresql+asyncpg://",)
        if not v.startswith(valid_prefixes):
            raise ValueError(
                "DATABASE_URL format incorrect. Supported: postgresql+asyncpg://"
            )
        return v


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"\n{'='*60}")
    print(f"Configuration Error: {e}")
    print(f"{'='*60}")
    print("\nPlease ensure .env file exists with required config:")
    print("  SECRET_KEY=your-secret-key-at-least-16-characters")
    print("  DATABASE_URL=postgresql+asyncpg://user:password@host:5432/rentwise")
    print(f"{'='*60}\n")
    raise
