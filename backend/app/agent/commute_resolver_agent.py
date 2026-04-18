"""LangGraph tool-use agent that resolves a candidate's HK coordinates.

Pipeline per step:

    plan (LLM) ──┬── tool_call ──▶ execute ──▶ (loop back to plan)
                 └── finish / give_up ─────────▶ END

The LLM picks among `als_geocode`, `amap_geocode`, `amap_poi_search`,
`finish`, and `give_up`. All geocoder tools funnel through the HK bbox gate
before returning an observation. ``MAX_STEPS`` caps runaway loops.

Used by :class:`CommuteService` when ``settings.COMMUTE_AGENT_ENABLED``;
falls back to a deterministic ladder when unavailable or unconfigured.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, TypedDict

from ..core.config import settings
from ..integrations.llm.utils import chat_completion_tools
from .prompts.commute_resolver_prompt import COMMUTE_RESOLVER_SYSTEM_PROMPT
from .tools.commute_tools import TOOL_EXECUTORS, TOOL_SCHEMAS, ToolContext

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - exercised in lightweight environments
    END = None
    StateGraph = None

logger = logging.getLogger(__name__)


PlannerFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], Awaitable[dict[str, Any]]]


class CommuteResolverState(TypedDict, total=False):
    candidate_facts: dict
    observations: list[dict]
    pending_tool_call: Optional[dict]
    resolved_coords: Optional[tuple[float, float]]
    resolved_via: Optional[str]
    give_up_reason: Optional[str]
    steps_taken: int


@dataclass
class CommuteResolverResult:
    resolved_coords: Optional[tuple[float, float]]
    resolved_via: Optional[str]
    give_up_reason: Optional[str]
    observations: list[dict]
    steps_taken: int


async def _default_planner(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> dict[str, Any]:
    """Call the configured LLM provider's tool-use endpoint."""
    return await chat_completion_tools(
        messages=messages,
        tools=tools,
        temperature=0.0,
    )


class CommuteResolverAgent:
    """Stateless agent — a single :meth:`ainvoke` does one full resolution."""

    def __init__(
        self,
        tool_context: ToolContext,
        *,
        planner: PlannerFn = _default_planner,
        max_steps: Optional[int] = None,
    ) -> None:
        self._ctx = tool_context
        self._planner = planner
        self._max_steps = max_steps or settings.COMMUTE_AGENT_MAX_STEPS
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def ainvoke(self, candidate_facts: dict) -> CommuteResolverResult:
        initial: CommuteResolverState = {
            "candidate_facts": candidate_facts,
            "observations": [],
            "pending_tool_call": None,
            "resolved_coords": None,
            "resolved_via": None,
            "give_up_reason": None,
            "steps_taken": 0,
        }
        if self._graph is None:
            state = await self._run_fallback_loop(initial)
        else:
            state = await self._graph.ainvoke(initial)
        return CommuteResolverResult(
            resolved_coords=state.get("resolved_coords"),
            resolved_via=state.get("resolved_via"),
            give_up_reason=state.get("give_up_reason"),
            observations=state.get("observations") or [],
            steps_taken=state.get("steps_taken") or 0,
        )

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    async def _plan_node(self, state: CommuteResolverState) -> CommuteResolverState:
        messages = self._build_messages(state)
        try:
            response = await self._planner(messages, TOOL_SCHEMAS)
        except Exception as exc:
            logger.warning("commute resolver planner raised: %s", exc)
            return {"give_up_reason": f"planner_error: {exc}"}
        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            content = (response.get("content") or "").strip()
            return {
                "give_up_reason": (
                    f"planner_returned_no_tool_call: {content[:200]}"
                    if content
                    else "planner_returned_no_tool_call"
                )
            }
        call = tool_calls[0]
        name = call.get("name")
        args = call.get("args") or {}

        if name == "finish":
            coords = args.get("coords")
            if (
                isinstance(coords, (list, tuple))
                and len(coords) == 2
                and all(isinstance(x, (int, float)) for x in coords)
            ):
                if self._coords_from_observations(state.get("observations") or [], tuple(coords)):
                    return {
                        "resolved_coords": (float(coords[0]), float(coords[1])),
                        "resolved_via": str(args.get("resolved_via") or "agent"),
                    }
                logger.warning(
                    "commute resolver: finish coords not seen in observations: %s", coords
                )
                return {
                    "give_up_reason": "finish_coords_not_from_observation",
                }
            return {"give_up_reason": "finish_missing_coords"}

        if name == "give_up":
            return {"give_up_reason": str(args.get("reason") or "give_up")}

        if name not in TOOL_EXECUTORS:
            return {"give_up_reason": f"unknown_tool: {name}"}

        return {"pending_tool_call": {"name": name, "args": args}}

    async def _execute_node(self, state: CommuteResolverState) -> CommuteResolverState:
        pending = state.get("pending_tool_call")
        if not pending:  # pragma: no cover - defensive, shouldn't happen
            return {"give_up_reason": "execute_without_pending_call"}
        executor = TOOL_EXECUTORS[pending["name"]]
        observation = await executor(pending.get("args") or {}, self._ctx)
        observations = list(state.get("observations") or [])
        observations.append(observation)
        return {
            "observations": observations,
            "pending_tool_call": None,
            "steps_taken": (state.get("steps_taken") or 0) + 1,
        }

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_after_plan(self, state: CommuteResolverState) -> str:
        if state.get("resolved_coords") is not None:
            return "end"
        if state.get("give_up_reason"):
            return "end"
        if state.get("pending_tool_call"):
            return "execute"
        return "end"

    def _route_after_execute(self, state: CommuteResolverState) -> str:
        if (state.get("steps_taken") or 0) >= self._max_steps:
            return "end"
        return "plan"

    # ------------------------------------------------------------------
    # Prompting
    # ------------------------------------------------------------------

    def _build_messages(self, state: CommuteResolverState) -> list[dict[str, Any]]:
        candidate_facts = state.get("candidate_facts") or {}
        observations = state.get("observations") or []
        steps_taken = state.get("steps_taken") or 0
        remaining = max(0, self._max_steps - steps_taken)
        user_content = (
            "Candidate facts (use these to craft tool queries):\n"
            + json.dumps(candidate_facts, ensure_ascii=False, indent=2)
            + f"\n\nSteps remaining: {remaining}\n"
            + "Previous observations (most recent last):\n"
            + (
                json.dumps(observations, ensure_ascii=False, indent=2)
                if observations
                else "(none yet)"
            )
            + "\n\nIssue exactly one tool call."
        )
        return [
            {"role": "system", "content": COMMUTE_RESOLVER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    # ------------------------------------------------------------------
    # Graph assembly
    # ------------------------------------------------------------------

    def _build_graph(self):
        if StateGraph is None:
            return None
        graph = StateGraph(CommuteResolverState)
        graph.add_node("plan", self._plan_node)
        graph.add_node("execute", self._execute_node)
        graph.set_entry_point("plan")
        graph.add_conditional_edges(
            "plan",
            self._route_after_plan,
            {"execute": "execute", "end": END},
        )
        graph.add_conditional_edges(
            "execute",
            self._route_after_execute,
            {"plan": "plan", "end": END},
        )
        return graph.compile()

    async def _run_fallback_loop(self, state: CommuteResolverState) -> CommuteResolverState:
        """Manual loop used when LangGraph is unavailable."""
        cur = dict(state)
        while True:
            cur.update(await self._plan_node(cur))
            if self._route_after_plan(cur) == "end":
                return cur
            cur.update(await self._execute_node(cur))
            if self._route_after_execute(cur) == "end":
                return cur

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coords_from_observations(observations: list[dict], target: tuple[float, float]) -> bool:
        target_lng, target_lat = target
        for obs in observations:
            if not obs.get("accepted"):
                continue
            coords = obs.get("coords")
            if not coords or len(coords) != 2:
                continue
            if abs(coords[0] - target_lng) < 1e-4 and abs(coords[1] - target_lat) < 1e-4:
                return True
        return False
