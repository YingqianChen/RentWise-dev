from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_import_service import build_combined_text, infer_source_type


class CandidateImportServiceTests(TestCase):
    def test_build_combined_text_includes_ocr_chunks(self):
        combined = build_combined_text(
            "Listing rent 18000",
            None,
            "Need to check deposit",
            "OCR block 1",
            "OCR block 2",
        )

        self.assertEqual(
            combined,
            "Listing rent 18000\n\nNeed to check deposit\n\nOCR block 1\n\nOCR block 2",
        )

    def test_infer_source_type_prefers_image_upload_for_image_only(self):
        self.assertEqual(
            infer_source_type(
                source_type=None,
                has_listing_text=False,
                has_chat_text=False,
                has_note_text=False,
                has_images=True,
            ),
            "image_upload",
        )
