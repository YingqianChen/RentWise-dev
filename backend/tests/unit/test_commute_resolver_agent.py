"""Unit tests for the commute resolver tool-use agent.

The agent is exercised with a scripted planner (no real LLM) and fake ALS /
Amap clients so we can assert on the exact observation trajectory.
"""

from __future__ import annotations

import json
from typing import Optional

import pytest

from app.agent.commute_resolver_agent import CommuteResolverAgent
from app.agent.tools.commute_tools import ToolContext


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeGeocoder:
    """Maps queries to canned coords (or None). Records every call."""

    def __init__(self, answers: dict[str, Optional[tuple[float, float]]]) -> None:
        self._answers = answers
        self.calls: list[str] = []

    async def geocode(self, query: str) -> Optional[tuple[float, float]]:
        self.calls.append(query)
        return self._answers.get(query)

    async def search_poi(self, query: str) -> Optional[tuple[float, float]]:
        self.calls.append(query)
        return self._answers.get(query)


class ScriptedPlanner:
    """Returns pre-scripted tool calls in order; records full prompt history."""

    def __init__(self, script: list[dict]) -> None:
        self._script = list(script)
        self.prompts: list[list[dict]] = []

    async def __call__(self, messages, tools):
        self.prompts.append(messages)
        if not self._script:
            raise AssertionError("ScriptedPlanner ran out of scripted responses")
        return self._script.pop(0)


def _tool_call(name: str, **args) -> dict:
    return {
        "tool_calls": [{"id": f"call_{name}", "name": name, "args": args}],
        "content": None,
        "finish_reason": "tool_calls",
    }


def _text_only(content: str) -> dict:
    return {"tool_calls": [], "content": content, "finish_reason": "stop"}


# HK coord samples
_HK_COORDS_ALS = (114.1809, 22.3282)   # Mong Kok East area
_HK_COORDS_GEO = (114.1720, 22.3190)
_SZ_COORDS = (114.0579, 22.6650)        # Out of HK bbox (Shenzhen core, lat > 22.56)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_finishes_on_first_accepted_coord():
    als = FakeGeocoder({"Mong Kok East": _HK_COORDS_ALS})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner(
        [
            _tool_call("als_geocode", query="Mong Kok East"),
            _tool_call(
                "finish",
                coords=[_HK_COORDS_ALS[0], _HK_COORDS_ALS[1]],
                resolved_via="als_geocode 'Mong Kok East'",
            ),
        ]
    )
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    result = await agent.ainvoke(
        {"nearest_station": "Mong Kok East", "district": "Yau Tsim Mong"}
    )

    assert result.resolved_coords == _HK_COORDS_ALS
    assert "als_geocode" in result.resolved_via
    assert result.give_up_reason is None
    assert len(result.observations) == 1
    assert result.observations[0]["accepted"] is True
    assert amap.calls == []  # ALS success should short-circuit Amap


@pytest.mark.asyncio
async def test_agent_retries_after_out_of_bbox_then_succeeds():
    als = FakeGeocoder({"Sha Tin Unit": _SZ_COORDS})
    amap = FakeGeocoder({"沙田第一城": _HK_COORDS_GEO})
    planner = ScriptedPlanner(
        [
            _tool_call("als_geocode", query="Sha Tin Unit"),
            _tool_call("amap_geocode", query="沙田第一城"),
            _tool_call(
                "finish",
                coords=[_HK_COORDS_GEO[0], _HK_COORDS_GEO[1]],
                resolved_via="amap_geocode '沙田第一城'",
            ),
        ]
    )
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    result = await agent.ainvoke(
        {"address_text": "Sha Tin Unit", "building_name": "沙田第一城"}
    )

    assert result.resolved_coords == _HK_COORDS_GEO
    assert result.observations[0]["accepted"] is False
    assert result.observations[0]["reason"] == "out_of_hk_bbox"
    assert result.observations[1]["accepted"] is True


@pytest.mark.asyncio
async def test_agent_gives_up_on_max_steps():
    als = FakeGeocoder({})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner(
        [_tool_call("als_geocode", query=f"attempt_{i}") for i in range(20)]
    )
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=3,
    )

    result = await agent.ainvoke({"district": "unknown"})

    assert result.resolved_coords is None
    assert result.steps_taken == 3


@pytest.mark.asyncio
async def test_agent_rejects_unknown_tool_name():
    als = FakeGeocoder({})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner([_tool_call("hallucinate", query="anything")])
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    result = await agent.ainvoke({"district": "Central"})

    assert result.resolved_coords is None
    assert result.give_up_reason is not None
    assert "hallucinate" in result.give_up_reason


@pytest.mark.asyncio
async def test_agent_rejects_fabricated_finish_coords():
    als = FakeGeocoder({})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner(
        [
            _tool_call(
                "finish",
                coords=[114.2, 22.3],  # never appeared in observations
                resolved_via="made up",
            )
        ]
    )
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    result = await agent.ainvoke({"district": "Central"})

    assert result.resolved_coords is None
    assert result.give_up_reason == "finish_coords_not_from_observation"


@pytest.mark.asyncio
async def test_agent_gives_up_when_planner_returns_text_only():
    als = FakeGeocoder({})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner([_text_only("I don't know how to proceed.")])
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    result = await agent.ainvoke({"district": "Central"})

    assert result.resolved_coords is None
    assert result.give_up_reason is not None
    assert result.give_up_reason.startswith("planner_returned_no_tool_call")


@pytest.mark.asyncio
async def test_agent_prompt_includes_candidate_facts_and_observations():
    """Each planner call should see the up-to-date observation history."""
    als = FakeGeocoder({"foo": _HK_COORDS_ALS})
    amap = FakeGeocoder({})
    planner = ScriptedPlanner(
        [
            _tool_call("als_geocode", query="foo"),
            _tool_call(
                "finish",
                coords=[_HK_COORDS_ALS[0], _HK_COORDS_ALS[1]],
                resolved_via="als 'foo'",
            ),
        ]
    )
    agent = CommuteResolverAgent(
        ToolContext(als=als, amap_geocode=amap, amap_poi=amap),
        planner=planner,
        max_steps=6,
    )

    facts = {"nearest_station": "foo", "district": "Central"}
    await agent.ainvoke(facts)

    first_prompt_user = planner.prompts[0][-1]["content"]
    assert "foo" in first_prompt_user
    assert "(none yet)" in first_prompt_user

    second_prompt_user = planner.prompts[1][-1]["content"]
    assert "als_geocode" in second_prompt_user
    # Observation JSON is embedded; make sure the accepted flag is carried through
    assert '"accepted": true' in second_prompt_user
