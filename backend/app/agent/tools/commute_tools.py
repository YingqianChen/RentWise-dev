"""Tool definitions for the commute resolver agent.

Each tool wraps an existing geocoder path (HK ALS, Amap geocode, Amap POI) and
funnels all coordinate returns through the HK bounding-box gate. The LLM never
sees raw coords that fall outside HK — a rejected lookup surfaces as an
observation with ``accepted: false`` and a ``reason`` so the model can choose
to rephrase and retry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Protocol

from ...integrations.als.client import AlsClient
from ...integrations.amap.client import AmapClient
from ...integrations.geocoding.hk_bbox import in_hk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimal structural protocols — easier to fake in unit tests than the concrete
# httpx-backed clients.
# ---------------------------------------------------------------------------


class _SupportsGeocode(Protocol):
    async def geocode(self, query: str) -> Optional[tuple[float, float]]:
        ...


class _SupportsPoi(Protocol):
    async def search_poi(self, query: str) -> Optional[tuple[float, float]]:
        ...


@dataclass
class ToolContext:
    """Dependency bundle injected when a tool is executed."""

    als: _SupportsGeocode
    amap_geocode: _SupportsGeocode
    amap_poi: _SupportsPoi


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI "function" format) + execute functions
# ---------------------------------------------------------------------------


def _observation(
    tool: str, query: str, coords: Optional[tuple[float, float]], reason: Optional[str] = None
) -> dict:
    if coords is None:
        return {
            "tool": tool,
            "query": query,
            "accepted": False,
            "reason": reason or "no_match",
        }
    if not in_hk(coords):
        return {
            "tool": tool,
            "query": query,
            "accepted": False,
            "reason": "out_of_hk_bbox",
            "rejected_coords": [round(coords[0], 5), round(coords[1], 5)],
        }
    return {
        "tool": tool,
        "query": query,
        "accepted": True,
        "coords": [round(coords[0], 5), round(coords[1], 5)],
    }


async def _als_geocode(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        return {"tool": "als_geocode", "accepted": False, "reason": "empty_query"}
    try:
        coords = await ctx.als.geocode(query)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("als_geocode raised for %r: %s", query, exc)
        coords = None
    return _observation("als_geocode", query, coords)


async def _amap_geocode(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        return {"tool": "amap_geocode", "accepted": False, "reason": "empty_query"}
    try:
        coords = await ctx.amap_geocode.geocode(query)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("amap_geocode raised for %r: %s", query, exc)
        coords = None
    return _observation("amap_geocode", query, coords)


async def _amap_poi_search(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        return {"tool": "amap_poi_search", "accepted": False, "reason": "empty_query"}
    try:
        coords = await ctx.amap_poi.search_poi(query)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("amap_poi_search raised for %r: %s", query, exc)
        coords = None
    return _observation("amap_poi_search", query, coords)


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "als_geocode",
            "description": (
                "Hong Kong government Address Lookup Service. Best for English "
                "HK place names (e.g. 'Mong Kok East MTR station', 'City One "
                "Shatin'). Returns a Hong Kong coordinate or a rejection reason."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free-text HK address, building, or station name.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_geocode",
            "description": (
                "Amap geocoding endpoint. Best for mainland-style addresses in "
                "Chinese. Returns a Hong Kong coordinate or a rejection reason."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Chinese-language HK address or building name.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_poi_search",
            "description": (
                "Amap POI keyword search. Last-ditch fallback for building "
                "names or landmarks that failed both geocoders. Returns a "
                "Hong Kong coordinate or a rejection reason."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword (building / landmark / station).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Call once you have an accepted coordinate from a previous "
                "observation. You MUST copy the coordinate array from an "
                "observation — never invent one. Supply a short explanation "
                "of which lookup succeeded."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coords": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "[longitude, latitude] from the winning observation.",
                    },
                    "resolved_via": {
                        "type": "string",
                        "description": "Short label, e.g. \"als_geocode 'Mong Kok East'\".",
                    },
                },
                "required": ["coords", "resolved_via"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "give_up",
            "description": (
                "Call when every viable query has been tried and failed. "
                "Include a brief reason so operators can triage later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
]


ToolFn = Callable[[dict, ToolContext], Awaitable[dict]]

TOOL_EXECUTORS: dict[str, ToolFn] = {
    "als_geocode": _als_geocode,
    "amap_geocode": _amap_geocode,
    "amap_poi_search": _amap_poi_search,
}


def build_default_context(amap_client: Optional[AmapClient]) -> ToolContext:
    """Construct a :class:`ToolContext` from the shared real clients.

    When *amap_client* is ``None`` the Amap tools still exist but will always
    return ``accepted: false`` — the agent can still try ALS.
    """

    class _NoAmap:
        async def geocode(self, query: str) -> None:
            return None

        async def search_poi(self, query: str) -> None:
            return None

    amap = amap_client if amap_client is not None else _NoAmap()
    return ToolContext(als=AlsClient(), amap_geocode=amap, amap_poi=amap)
