"""Tests for the multi-route selection / labeling logic in AmapClient."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.integrations.amap.client import (
    _route_signature,
    _select_primary_and_alternatives,
)


def _walk(meters: int, mins: int = 1) -> dict:
    return {
        "mode": "walking",
        "line_name": None,
        "from_station": None,
        "to_station": None,
        "duration_minutes": mins,
        "distance_meters": meters,
    }


def _ride(mode: str, line: str, from_st: str, to_st: str, mins: int) -> dict:
    return {
        "mode": mode,
        "line_name": line,
        "from_station": from_st,
        "to_station": to_st,
        "duration_minutes": mins,
        "distance_meters": None,
    }


def _route(duration: int, segments: list[dict]) -> dict:
    return {
        "duration_minutes": duration,
        "origin_station": next(
            (s["from_station"] for s in segments if s["mode"] != "walking"), None
        ),
        "destination_station": next(
            (s["to_station"] for s in reversed(segments) if s["mode"] != "walking"),
            None,
        ),
        "segments": segments,
        "route_summary": " · ".join(
            s.get("line_name") or "Walk" for s in segments
        ),
    }


class RouteSignatureTests(unittest.TestCase):
    def test_walking_jitter_does_not_change_signature(self):
        a = _route(22, [_walk(80), _ride("subway", "MTR", "Tsuen Wan", "Central", 18), _walk(50)])
        b = _route(23, [_walk(120), _ride("subway", "MTR", "Tsuen Wan", "Central", 18), _walk(40)])
        self.assertEqual(_route_signature(a), _route_signature(b))

    def test_different_lines_yield_different_signature(self):
        a = _route(22, [_walk(80), _ride("subway", "MTR Tsuen Wan Line", "Tsuen Wan", "Central", 18), _walk(50)])
        b = _route(28, [_walk(80), _ride("bus", "Bus 102", "Tsuen Wan", "Central", 22), _walk(50)])
        self.assertNotEqual(_route_signature(a), _route_signature(b))


class SelectionTests(unittest.TestCase):
    def test_fastest_becomes_primary(self):
        slow = _route(35, [_walk(200), _ride("bus", "Bus", "A", "B", 30)])
        fast = _route(22, [_walk(50), _ride("subway", "MTR", "A", "B", 18), _walk(40)])
        primary, alts = _select_primary_and_alternatives([slow, fast])
        self.assertEqual(primary["duration_minutes"], 22)

    def test_fewer_transfers_label_when_alternative_has_fewer_legs(self):
        # Primary: walk + MTR + walk + Bus + walk (3 legs, 2 transfers)
        primary_route = _route(
            22,
            [
                _walk(50),
                _ride("subway", "MTR", "A", "B", 10),
                _walk(40),
                _ride("bus", "Bus", "B", "C", 8),
                _walk(20),
            ],
        )
        # Alt: walk + MTR direct (1 transfer-leg, 0 transfers)
        direct = _route(28, [_walk(80), _ride("subway", "MTR Direct", "A", "C", 25)])
        primary, alts = _select_primary_and_alternatives([primary_route, direct])
        self.assertEqual(primary["duration_minutes"], 22)
        labels = [alt["label"] for alt in alts]
        self.assertIn("Fewer transfers", labels)

    def test_less_walking_label_when_alternative_walks_less(self):
        # Primary: long walking + short ride
        primary_route = _route(
            22, [_walk(800), _ride("subway", "MTR", "A", "B", 5), _walk(600)]
        )
        # Alt: minimal walking + longer ride
        less_walk = _route(
            28, [_walk(50), _ride("bus", "Bus", "A", "B", 25), _walk(50)]
        )
        primary, alts = _select_primary_and_alternatives([primary_route, less_walk])
        labels = [alt["label"] for alt in alts]
        self.assertIn("Less walking", labels)

    def test_dedupes_identical_routes(self):
        a = _route(22, [_walk(80), _ride("subway", "MTR", "A", "B", 18), _walk(40)])
        b = _route(23, [_walk(120), _ride("subway", "MTR", "A", "B", 18), _walk(50)])
        primary, alts = _select_primary_and_alternatives([a, b])
        self.assertEqual(alts, [])  # dedup → only one distinct route → no alternatives

    def test_generic_alternative_when_no_specialized_label(self):
        # Two distinct routes, both with 2 ride legs and similar walking.
        # Neither qualifies for "Fewer transfers" or "Less walking" → generic.
        a = _route(
            22,
            [
                _walk(100),
                _ride("subway", "Line A", "X", "Y", 10),
                _walk(60),
                _ride("bus", "Bus 1", "Y", "Z", 8),
            ],
        )
        b = _route(
            25,
            [
                _walk(100),
                _ride("subway", "Line B", "X", "W", 12),
                _walk(60),
                _ride("bus", "Bus 2", "W", "Z", 10),
            ],
        )
        primary, alts = _select_primary_and_alternatives([a, b])
        self.assertEqual(len(alts), 1)
        self.assertEqual(alts[0]["label"], "Alternative")

    def test_only_one_route_has_no_alternatives(self):
        only = _route(22, [_walk(80), _ride("subway", "MTR", "A", "B", 18), _walk(40)])
        primary, alts = _select_primary_and_alternatives([only])
        self.assertEqual(alts, [])


if __name__ == "__main__":
    unittest.main()
