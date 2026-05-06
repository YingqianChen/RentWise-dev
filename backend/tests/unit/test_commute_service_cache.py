"""Unit tests for the new commute caching primitives.

Covers the two pure helpers (signature + departure window translation) plus
the read/write cache roundtrip against a fake AsyncSession. The full
``build_for_candidate`` orchestration is left to integration coverage —
mocking the entire LangGraph + Amap stack here would test the mocks more
than the code.
"""

from __future__ import annotations

import sys
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateCommuteEvidence
from app.schemas.commute import CommuteEvidence, CommuteSegment
from app.services.commute_service import (
    CommuteService,
    _compute_config_signature,
    _resolve_departure,
)
from tests.helpers import build_candidate, build_project, build_user


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeAsyncSession:
    """Minimal AsyncSession stand-in for cache read/write tests."""

    def __init__(self, existing_row=None):
        self._row = existing_row
        self.added: list = []
        self.flushed_count = 0

    async def execute(self, _stmt):
        return _FakeResult(self._row)

    def add(self, obj):
        self.added.append(obj)
        self._row = obj  # subsequent reads see what we just added

    async def flush(self):
        self.flushed_count += 1


class ConfigSignatureTests(unittest.TestCase):
    def test_signature_changes_when_destination_changes(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        candidate.extracted_info.address_text = "1 Connaught Road Central"

        project.commute_destination_query = "Admiralty Station"
        sig_a = _compute_config_signature(project, candidate)

        project.commute_destination_query = "Causeway Bay Station"
        sig_b = _compute_config_signature(project, candidate)

        self.assertNotEqual(sig_a, sig_b)

    def test_signature_changes_when_departure_window_changes(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        project.commute_destination_query = "Admiralty Station"
        project.commute_mode = "transit"

        project.commute_departure_window = "now"
        sig_now = _compute_config_signature(project, candidate)

        project.commute_departure_window = "peak_morning"
        sig_peak = _compute_config_signature(project, candidate)

        self.assertNotEqual(sig_now, sig_peak)

    def test_signature_changes_when_candidate_address_changes(self):
        user = build_user()
        project = build_project(user)
        project.commute_destination_query = "Admiralty Station"

        candidate = build_candidate(project)
        candidate.extracted_info.address_text = "1 Connaught Road"
        sig_a = _compute_config_signature(project, candidate)

        candidate.extracted_info.address_text = "5 Garden Road"
        sig_b = _compute_config_signature(project, candidate)

        self.assertNotEqual(sig_a, sig_b)


class DepartureResolverTests(unittest.TestCase):
    def test_now_returns_none(self):
        user = build_user()
        project = build_project(user)
        project.commute_departure_window = "now"
        self.assertEqual(_resolve_departure(project), (None, None))

    def test_peak_morning_returns_weekday_at_0830(self):
        user = build_user()
        project = build_project(user)
        project.commute_departure_window = "peak_morning"
        date_str, time_str = _resolve_departure(project)
        self.assertIsNotNone(date_str)
        self.assertEqual(time_str, "08:30")
        # Resolved datetime must be a weekday (Mon=0..Fri=4)
        resolved = datetime.strptime(date_str, "%Y-%m-%d")
        self.assertLess(resolved.weekday(), 5)

    def test_custom_returns_user_time_on_weekday(self):
        user = build_user()
        project = build_project(user)
        project.commute_departure_window = "custom"
        project.commute_departure_time = "17:45"
        date_str, time_str = _resolve_departure(project)
        self.assertIsNotNone(date_str)
        self.assertEqual(time_str, "17:45")
        resolved = datetime.strptime(date_str, "%Y-%m-%d")
        self.assertLess(resolved.weekday(), 5)

    def test_custom_with_invalid_time_falls_back_to_now(self):
        user = build_user()
        project = build_project(user)
        project.commute_departure_window = "custom"
        project.commute_departure_time = "not-a-time"
        self.assertEqual(_resolve_departure(project), (None, None))


class CacheRoundtripTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_then_read_returns_evidence(self):
        service = CommuteService()
        candidate_id = uuid.uuid4()
        evidence = CommuteEvidence(
            status="ready",
            estimated_minutes=22,
            mode="transit",
            route_summary="Walk → MTR Tsuen Wan Line → Walk",
            origin_station="Tsuen Wan",
            destination_station="Admiralty",
            segments=[
                CommuteSegment(mode="walking", duration_minutes=3),
                CommuteSegment(
                    mode="subway", line_name="港铁荃湾线", duration_minutes=18
                ),
                CommuteSegment(mode="walking", duration_minutes=1),
            ],
            destination_label="Admiralty Station",
            confidence_note=None,
        )

        db = FakeAsyncSession(existing_row=None)
        await service._write_cache(db, candidate_id, "sig-abc", evidence)

        # The added row should be a CandidateCommuteEvidence instance
        self.assertEqual(len(db.added), 1)
        row = db.added[0]
        self.assertIsInstance(row, CandidateCommuteEvidence)
        self.assertEqual(row.config_signature, "sig-abc")
        self.assertEqual(row.estimated_minutes, 22)
        self.assertEqual(len(row.segments), 3)

        # Reading with the matching signature reconstructs CommuteEvidence
        cached = await service._read_cache(db, candidate_id, "sig-abc")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.status, "ready")
        self.assertEqual(cached.estimated_minutes, 22)
        self.assertEqual(len(cached.segments), 3)
        self.assertEqual(cached.segments[1].line_name, "港铁荃湾线")

    async def test_read_returns_none_on_signature_mismatch(self):
        service = CommuteService()
        candidate_id = uuid.uuid4()
        existing = CandidateCommuteEvidence(
            candidate_id=candidate_id,
            config_signature="old-sig",
            status="ready",
            estimated_minutes=30,
            mode="transit",
            route_summary=None,
            origin_station=None,
            destination_station=None,
            segments=None,
            destination_label="Old",
            confidence_note=None,
        )
        db = FakeAsyncSession(existing_row=existing)

        cached = await service._read_cache(db, candidate_id, "new-sig")
        self.assertIsNone(cached)

    async def test_write_skips_uncacheable_status(self):
        service = CommuteService()
        candidate_id = uuid.uuid4()
        db = FakeAsyncSession(existing_row=None)

        # not_configured and insufficient_candidate_location must NOT cache —
        # they reflect input gaps the caller may fill in shortly.
        for status in ("not_configured", "insufficient_candidate_location"):
            await service._write_cache(
                db, candidate_id, "sig", CommuteEvidence(status=status)
            )
        self.assertEqual(db.added, [])
        self.assertEqual(db.flushed_count, 0)


if __name__ == "__main__":
    unittest.main()
