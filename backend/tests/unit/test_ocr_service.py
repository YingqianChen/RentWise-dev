from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ocr_service import OCRService


class _FakeResult:
    def __init__(self, rec_texts):
        self.rec_texts = rec_texts


class OCRServiceTests(TestCase):
    def setUp(self):
        OCRService._shared_engines = {}

    def test_collect_text_lines_supports_predict_result_objects(self):
        service = OCRService()
        lines = service._collect_text_lines([
            _FakeResult(["Rent: $5800/month", "Sham Shui Po", "2 Months Deposit"])
        ])

        self.assertEqual(
            lines,
            ["Rent: $5800/month", "Sham Shui Po", "2 Months Deposit"],
        )

    def test_collect_text_lines_supports_rapidocr_result_shapes(self):
        service = OCRService()
        lines = service._collect_text_lines(
            (
                [
                    [[[0, 0], [1, 0], [1, 1], [0, 1]], "Monthly rent $18,000", 0.99],
                    [[[0, 2], [1, 2], [1, 3], [0, 3]], "Need 2 months deposit", 0.97],
                ],
                0.032,
            )
        )

        self.assertEqual(lines, ["Monthly rent $18,000", "Need 2 months deposit"])

    @patch("app.services.ocr_service.settings.OCR_PROVIDER", "rapidocr")
    def test_get_engine_uses_rapidocr_by_default(self):
        service = OCRService()
        fake_ctor = SimpleNamespace()
        fake_ctor.RapidOCR = lambda: "rapid-engine"

        with patch("app.services.ocr_service.importlib.import_module", return_value=fake_ctor) as import_module:
            self.assertEqual(service._get_engine(), "rapid-engine")

        import_module.assert_called_once_with("rapidocr_onnxruntime")

    @patch("app.services.ocr_service.settings.OCR_PROVIDER", "paddleocr")
    def test_get_engine_uses_speed_focused_paddle_defaults(self):
        service = OCRService()

        with patch("app.services.ocr_service.importlib.import_module") as import_module:
            paddle_ocr_cls = import_module.return_value.PaddleOCR
            service._get_engine()

        import_module.assert_called_once_with("paddleocr")
        paddle_ocr_cls.assert_called_once_with(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
