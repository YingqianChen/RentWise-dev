from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_analysis_state import has_usable_analysis
from tests.helpers import build_candidate, build_project, build_user


class CandidateAnalysisStateTests(TestCase):
    def test_completed_candidate_with_all_records_is_usable(self):
        candidate = build_candidate(build_project(build_user()))

        self.assertTrue(has_usable_analysis(candidate))

    def test_old_records_are_not_usable_while_processing_or_failed(self):
        candidate = build_candidate(build_project(build_user()))

        for stage in ("queued", "running_ocr", "extracting", "assessing", "failed", None):
            candidate.processing_stage = stage
            with self.subTest(stage=stage):
                self.assertFalse(has_usable_analysis(candidate))

    def test_completed_candidate_missing_any_required_record_is_not_usable(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.cost_assessment = None

        self.assertFalse(has_usable_analysis(candidate))

    def test_legacy_candidate_without_all_core_field_facts_requires_reanalysis(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.field_facts.pop()

        self.assertFalse(has_usable_analysis(candidate))
