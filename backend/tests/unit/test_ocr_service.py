from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ocr_service import PaddleOCRService


class _FakeResult:
    def __init__(self, rec_texts):
        self.rec_texts = rec_texts


class OCRServiceTests(TestCase):
    def test_collect_text_lines_supports_predict_result_objects(self):
        service = PaddleOCRService()
        lines = service._collect_text_lines([
            _FakeResult(["Rent: $5800/month", "Sham Shui Po", "2 Months Deposit"])
        ])

        self.assertEqual(
            lines,
            ["Rent: $5800/month", "Sham Shui Po", "2 Months Deposit"],
        )

    def test_get_engine_uses_speed_focused_defaults(self):
        service = PaddleOCRService()

        with patch("paddleocr.PaddleOCR") as paddle_ocr_cls:
            service._get_engine()

        paddle_ocr_cls.assert_called_once_with(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
