"""Configuration management using pydantic-settings."""

from pathlib import Path

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

    # Amap (高德地图) for commute estimation
    AMAP_API_KEY: str = ""

    # Application
    APP_ENV: str = "development"  # development | production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    FILE_STORAGE_PROVIDER: str = "local"
    LOCAL_UPLOAD_ROOT: str = str(Path(__file__).resolve().parents[2] / "storage")
    OCR_PROVIDER: str = "rapidocr"
    MISTRAL_API_KEY: str = ""
    MISTRAL_OCR_MODEL: str = "mistral-ocr-latest"
    OCR_SPACE_API_KEY: str = ""
    PADDLEOCR_LANG: str = "ch"
    OCR_USE_DOC_ORIENTATION: bool = False
    OCR_USE_DOC_UNWARPING: bool = False
    OCR_USE_TEXTLINE_ORIENTATION: bool = False
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK: bool = True
    LOW_MEMORY_MODE: bool = False
    OCR_PREWARM_ON_STARTUP: bool = True
    OCR_MAX_IMAGE_DIMENSION: int = 1600

    @field_validator("OCR_PROVIDER")
    @classmethod
    def validate_ocr_provider(cls, v: str) -> str:
        """Validate supported OCR backends."""
        normalized = v.strip().lower()
        if normalized not in {"rapidocr", "paddleocr", "mistral", "ocr_space"}:
            raise ValueError(
                "OCR_PROVIDER must be one of `rapidocr`, `paddleocr`, `mistral`, `ocr_space`"
            )
        return normalized

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Accept comma-separated CORS origins."""
        parsed = [origin.strip() for origin in v.split(",") if origin.strip()]
        if not parsed:
            return "http://localhost:3000,http://127.0.0.1:3000"
        return ",".join(parsed)

    @property
    def backend_cors_origins_list(self) -> list[str]:
        """Return the configured CORS origins as a normalized list."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def effective_ocr_prewarm_on_startup(self) -> bool:
        """Disable eager OCR warmup when low-memory protection is enabled."""
        return self.OCR_PREWARM_ON_STARTUP and not self.LOW_MEMORY_MODE

    @property
    def effective_ocr_max_image_dimension(self) -> int:
        """Clamp OCR image size more aggressively in low-memory deployments."""
        if not self.LOW_MEMORY_MODE:
            return self.OCR_MAX_IMAGE_DIMENSION
        if self.OCR_MAX_IMAGE_DIMENSION <= 0:
            return 1400
        return min(self.OCR_MAX_IMAGE_DIMENSION, 1400)

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
        """Validate and normalize database URL format."""
        if not v:
            raise ValueError("DATABASE_URL must be set in .env file")

        normalized = v.strip()
        if normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized[len("postgres://") :]

        if normalized.startswith("postgresql://") and not normalized.startswith(
            "postgresql+asyncpg://"
        ):
            normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]

        normalized = normalized.replace("sslmode=require", "ssl=require")

        if not normalized.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL format incorrect. Supported: postgresql+asyncpg:// "
                "(the app also auto-normalizes postgres:// and postgresql:// URLs)."
            )
        return normalized


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
