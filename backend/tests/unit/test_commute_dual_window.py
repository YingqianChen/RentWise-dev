"""Unit tests for the peak_both dual-window flow.

Covers two layers:
- ``_resolve_dual_departure`` — pure helper that produces (AM, PM) pairs.
- The peak_both branch in ``build_for_candidate`` — verifies that the service
  invokes the per-window calculation twice with distinct departure times and
  returns a single ``CommuteEvidence`` whose ``paired_evidence`` carries the
  evening half.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.schemas.commute import CommuteEvidence
from app.services.commute_service import CommuteService, _resolve_dual_departure
from tests.helpers import build_candidate, build_project, build_user


class ResolveDualDepartureTests(unittest.TestCase):
    def test_returns_two_pairs_at_0830_and_1830_on_weekdays(self):
        user = build_user()
        project = build_project(user)
        project.commute_departure_window = "peak_both"

        (am_date, am_time), (pm_date, pm_time) = _resolve_dual_departure(project)

        self.assertEqual(am_time, "08:30")
        self.assertEqual(pm_time, "18:30")
        self.assertIsNotNone(am_date)
        self.assertIsNotNone(pm_date)
        # Both must land on a weekday (Mon=0..Fri=4).
        for d in (am_date, pm_date):
            self.assertLess(datetime.strptime(d, "%Y-%m-%d").weekday(), 5)


class PeakBothBranchTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_two_window_calculations_and_pairs_evening(self):
        """End-to-end: peak_both → 2 calls → morning is primary, evening paired."""
        user = build_user()
        project = build_project(user)
        project.commute_enabled = True
        project.commute_destination_query = "Central"
        # Cached HK destination coords skip the geocoder entirely.
        project.commute_destination_lat = 22.28
        project.commute_destination_lng = 114.15
        project.commute_mode = "transit"
        project.commute_departure_window = "peak_both"

        candidate = build_candidate(project)
        candidate.extracted_info.address_text = "Tsuen Wan"

        service = CommuteService()
        # _client must be truthy or build_for_candidate short-circuits with
        # "Map service not configured".
        service._client = AsyncMock()

        recorded: list[tuple[str | None, str | None]] = []

        async def fake_evidence(_p, _c, _cc, _dc, dl, dep_date, dep_time):
            recorded.append((dep_date, dep_time))
            return CommuteEvidence(
                status="ready",
                estimated_minutes=22 if dep_time == "08:30" else 38,
                mode="transit",
                destination_label=dl,
            )

        with patch(
            "app.services.commute_service.settings.COMMUTE_AGENT_ENABLED", False
        ), patch.object(
            service,
            "_deterministic_resolve",
            new=AsyncMock(return_value=((114.10, 22.37), "test", [])),
        ), patch.object(service, "_evidence_for_window", new=fake_evidence):
            evidence = await service.build_for_candidate(project, candidate, db=None)

        # Two window computations, in AM-then-PM order.
        self.assertEqual(len(recorded), 2)
        self.assertEqual(recorded[0][1], "08:30")
        self.assertEqual(recorded[1][1], "18:30")

        # Morning is the outer evidence.
        self.assertEqual(evidence.estimated_minutes, 22)
        self.assertIsNotNone(evidence.paired_evidence)
        self.assertEqual(evidence.paired_evidence.estimated_minutes, 38)
        # One-level nesting invariant.
        self.assertIsNone(evidence.paired_evidence.paired_evidence)


if __name__ == "__main__":
    unittest.main()
