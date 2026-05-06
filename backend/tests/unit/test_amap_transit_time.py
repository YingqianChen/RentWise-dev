"""Verify route_transit forwards departure date/time to Amap."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.integrations.amap.client import AmapClient


class AmapTransitTimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_transit_omits_time_params_when_absent(self):
        client = AmapClient("test-key")
        captured: dict = {}

        async def fake_get(path, params):
            captured["path"] = path
            captured["params"] = dict(params)
            return None  # short-circuit; we only need the params

        with patch.object(client, "_get", side_effect=fake_get):
            await client.route_transit("114.1,22.3", "114.2,22.4")

        self.assertEqual(captured["path"], "/v3/direction/transit/integrated")
        self.assertNotIn("date", captured["params"])
        self.assertNotIn("time", captured["params"])

    async def test_transit_forwards_time_params_when_provided(self):
        client = AmapClient("test-key")
        captured: dict = {}

        async def fake_get(path, params):
            captured["params"] = dict(params)
            return None

        with patch.object(client, "_get", side_effect=fake_get):
            await client.route_transit(
                "114.1,22.3", "114.2,22.4", date="2026-05-08", time="08:30"
            )

        self.assertEqual(captured["params"].get("date"), "2026-05-08")
        self.assertEqual(captured["params"].get("time"), "08:30")

    async def test_transit_skips_time_when_only_one_provided(self):
        client = AmapClient("test-key")
        captured: dict = {}

        async def fake_get(path, params):
            captured["params"] = dict(params)
            return None

        with patch.object(client, "_get", side_effect=fake_get):
            # Only date, no time → both omitted (Amap ignores half-spec'd timing).
            await client.route_transit("114.1,22.3", "114.2,22.4", date="2026-05-08")

        self.assertNotIn("date", captured["params"])
        self.assertNotIn("time", captured["params"])


if __name__ == "__main__":
    unittest.main()
