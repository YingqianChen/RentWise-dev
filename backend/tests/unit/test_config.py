from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import Settings


class SettingsTests(TestCase):
    def _build_settings(self, **overrides) -> Settings:
        data = {
            "SECRET_KEY": "1234567890123456",
            "DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/rentwise",
        }
        data.update(overrides)
        return Settings(**data)

    def test_cors_origins_accept_comma_separated_string(self):
        settings = self._build_settings(
            BACKEND_CORS_ORIGINS="https://rentwise.vercel.app, https://rentwise-api.onrender.com"
        )

        self.assertEqual(
            settings.backend_cors_origins_list,
            ["https://rentwise.vercel.app", "https://rentwise-api.onrender.com"],
        )

    def test_cors_origins_fallback_to_local_defaults_when_blank(self):
        settings = self._build_settings(BACKEND_CORS_ORIGINS="")

        self.assertEqual(
            settings.backend_cors_origins_list,
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        )

    def test_database_url_normalizes_standard_postgresql_url(self):
        settings = self._build_settings(
            DATABASE_URL="postgresql://user:password@localhost:5432/rentwise?sslmode=require"
        )

        self.assertEqual(
            settings.DATABASE_URL,
            "postgresql+asyncpg://user:password@localhost:5432/rentwise?ssl=require",
        )

    def test_database_url_normalizes_postgres_shorthand_url(self):
        settings = self._build_settings(
            DATABASE_URL="postgres://user:password@localhost:5432/rentwise"
        )

        self.assertEqual(
            settings.DATABASE_URL,
            "postgresql+asyncpg://user:password@localhost:5432/rentwise",
        )

    def test_low_memory_mode_disables_effective_prewarm(self):
        settings = self._build_settings(
            LOW_MEMORY_MODE=True,
            OCR_PREWARM_ON_STARTUP=True,
        )

        self.assertFalse(settings.effective_ocr_prewarm_on_startup)

    def test_low_memory_mode_clamps_effective_image_dimension(self):
        settings = self._build_settings(
            LOW_MEMORY_MODE=True,
            OCR_MAX_IMAGE_DIMENSION=2200,
        )

        self.assertEqual(settings.effective_ocr_max_image_dimension, 1400)
