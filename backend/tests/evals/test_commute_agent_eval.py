"""End-to-end commute resolver eval.

This exercise requires both ``GROQ_API_KEY`` (for the agent LLM planner) and
``AMAP_API_KEY`` (for the actual routing + geocoding calls). When either is
missing the test is skipped. Run with::

    GROQ_API_KEY=... AMAP_API_KEY=... pytest -m eval backend/tests/evals/test_commute_agent_eval.py -q
"""

from __future__ import annotations

import os

import pytest

if not os.getenv("GROQ_API_KEY"):
    pytest.skip("GROQ_API_KEY not set; eval suite skipped", allow_module_level=True)

from app.agent.commute_resolver_agent import CommuteResolverAgent  # noqa: E402
from app.agent.tools.commute_tools import ToolContext  # noqa: E402
from app.integrations.als.client import AlsClient  # noqa: E402
from app.integrations.amap.client import AmapClient  # noqa: E402

from .scoring import CaseResult, FieldResult, aggregate_report, fuzzy_field_match, numeric_in_range  # noqa: E402

_ORIGIN_STATION_FLOOR = 0.50
_MODE_FLOOR = 0.70
_MINUTES_FLOOR = 0.50

pytestmark = pytest.mark.eval


async def test_commute_agent_golden_set(golden_commutes, eval_report_writer):
    if not golden_commutes:
        pytest.skip("no golden_commutes.jsonl samples loaded")
    amap_key = os.getenv("AMAP_API_KEY")
    if not amap_key:
        pytest.skip("AMAP_API_KEY not set")

    amap = AmapClient(amap_key)
    agent = CommuteResolverAgent(
        ToolContext(als=AlsClient(), amap_geocode=amap, amap_poi=amap)
    )

    results: list[CaseResult] = []
    for sample in golden_commutes:
        candidate_facts = sample["candidate_facts"]
        expected = sample["expected"]
        mode = sample.get("mode") or "transit"

        resolution = await agent.ainvoke(candidate_facts)
        field_results: list[FieldResult] = []

        if resolution.resolved_coords is None:
            # Total failure — record all expected fields as misses.
            for k in ("origin_station", "mode", "minutes"):
                if k == "origin_station" and "origin_station_any_of" in expected:
                    field_results.append(FieldResult(k, False, expected["origin_station_any_of"], None))
                if k == "mode" and "mode_any_of" in expected:
                    field_results.append(FieldResult(k, False, expected["mode_any_of"], None))
                if k == "minutes" and "minutes_range" in expected:
                    field_results.append(FieldResult(k, False, expected["minutes_range"], None))
            results.append(CaseResult(sample["id"], field_results))
            continue

        # Run routing for the resolved coordinate
        dest = sample["project_destination"]
        dest_coords = await amap.geocode(dest) or await amap.search_poi(dest)
        if dest_coords is None:
            pytest.fail(f"destination '{dest}' could not be geocoded; bad fixture")

        origin_str = f"{resolution.resolved_coords[0]},{resolution.resolved_coords[1]}"
        dest_str = f"{dest_coords[0]},{dest_coords[1]}"
        if mode == "transit":
            route = await amap.route_transit(origin_str, dest_str)
        elif mode == "driving":
            route = await amap.route_driving(origin_str, dest_str)
        else:
            route = await amap.route_walking(origin_str, dest_str)

        if "origin_station_any_of" in expected:
            actual_station = (route or {}).get("origin_station")
            passed = fuzzy_field_match(expected["origin_station_any_of"], actual_station)
            field_results.append(FieldResult("origin_station", passed, expected["origin_station_any_of"], actual_station))
        if "mode_any_of" in expected:
            segments = (route or {}).get("segments") or []
            non_walking = [s for s in segments if s.get("mode") != "walking"]
            actual_mode = non_walking[0].get("mode") if non_walking else None
            passed = fuzzy_field_match(expected["mode_any_of"], actual_mode)
            field_results.append(FieldResult("mode", passed, expected["mode_any_of"], actual_mode))
        if "minutes_range" in expected:
            actual_min = (route or {}).get("duration_minutes")
            passed = actual_min is not None and numeric_in_range(actual_min, expected["minutes_range"])
            field_results.append(FieldResult("minutes", passed, expected["minutes_range"], actual_min))

        results.append(CaseResult(sample["id"], field_results))

    report = aggregate_report(results)
    eval_report_writer("commute_last_run.json", report)

    per_field = report["per_field"]
    floors = {
        "origin_station": _ORIGIN_STATION_FLOOR,
        "mode": _MODE_FLOOR,
        "minutes": _MINUTES_FLOOR,
    }
    violations: list[str] = []
    for field_name, floor in floors.items():
        if field_name not in per_field:
            continue
        rate = per_field[field_name]["pass_rate"]
        if rate < floor:
            violations.append(f"{field_name}: {rate:.2f} < floor {floor:.2f}")

    assert not violations, "commute eval regressions:\n" + "\n".join(violations)
