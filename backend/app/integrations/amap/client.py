"""Async client for Amap (高德地图) REST API — geocoding and route planning."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://restapi.amap.com"
_TIMEOUT = 10.0


class AmapClient:
    """Thin async wrapper around Amap Web Service API endpoints."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    async def geocode(self, address: str, city: str = "香港") -> Optional[tuple[float, float]]:
        """Geocode *address* → ``(longitude, latitude)`` or *None*.

        If the first attempt returns no results, retries with "香港" appended
        to help Amap resolve English or ambiguous place names.
        """
        result = await self._geocode_once(address, city)
        if result is not None:
            return result
        # Retry with explicit Hong Kong suffix for English addresses
        if "香港" not in address and "Hong Kong" not in address:
            return await self._geocode_once(f"{address} 香港", city)
        return None

    async def _geocode_once(self, address: str, city: str) -> Optional[tuple[float, float]]:
        """Single geocode attempt."""
        params = {"key": self._api_key, "address": address, "city": city}
        data = await self._get("/v3/geocode/geo", params)
        if data is None:
            return None
        geocodes = data.get("geocodes") or []
        if not geocodes:
            logger.warning("Amap geocode returned no results for %r", address)
            return None
        location = geocodes[0].get("location", "")
        try:
            lng, lat = location.split(",")
            return float(lng), float(lat)
        except (ValueError, AttributeError):
            logger.warning("Amap geocode: bad location format %r", location)
            return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def route_transit(
        self, origin: str, destination: str, city: str = "香港"
    ) -> Optional[dict]:
        """Transit routing → ``{duration_minutes, route_summary}`` or *None*."""
        params = {
            "key": self._api_key,
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": city,
        }
        data = await self._get("/v3/direction/transit/integrated", params)
        if data is None:
            return None
        route = data.get("route") or {}
        transits = route.get("transits") or []
        if not transits:
            logger.warning("Amap transit: no routes for %s → %s", origin, destination)
            return None
        best = transits[0]
        try:
            duration_sec = int(best.get("duration", 0))
        except (TypeError, ValueError):
            duration_sec = 0
        segments = best.get("segments") or []
        summary_parts = []
        for seg in segments[:3]:
            bus = seg.get("bus", {})
            buslines = bus.get("buslines") or []
            if buslines:
                summary_parts.append(buslines[0].get("name", ""))
        route_summary = " → ".join(filter(None, summary_parts)) or None
        return {"duration_minutes": max(1, round(duration_sec / 60)), "route_summary": route_summary}

    async def route_driving(self, origin: str, destination: str) -> Optional[dict]:
        """Driving routing → ``{duration_minutes, route_summary}`` or *None*."""
        params = {
            "key": self._api_key,
            "origin": origin,
            "destination": destination,
        }
        data = await self._get("/v3/direction/driving", params)
        if data is None:
            return None
        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            logger.warning("Amap driving: no paths for %s → %s", origin, destination)
            return None
        best = paths[0]
        try:
            duration_sec = int(best.get("duration", 0))
        except (TypeError, ValueError):
            duration_sec = 0
        return {"duration_minutes": max(1, round(duration_sec / 60)), "route_summary": None}

    async def route_walking(self, origin: str, destination: str) -> Optional[dict]:
        """Walking routing → ``{duration_minutes, route_summary}`` or *None*."""
        params = {
            "key": self._api_key,
            "origin": origin,
            "destination": destination,
        }
        data = await self._get("/v3/direction/walking", params)
        if data is None:
            return None
        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            logger.warning("Amap walking: no paths for %s → %s", origin, destination)
            return None
        best = paths[0]
        try:
            duration_sec = int(best.get("duration", 0))
        except (TypeError, ValueError):
            duration_sec = 0
        return {"duration_minutes": max(1, round(duration_sec / 60)), "route_summary": None}

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict) -> Optional[dict]:
        """Issue a GET request and return the parsed JSON body, or *None* on any error."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{_BASE}{path}", params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") != "1":
                logger.warning("Amap API error on %s: %s", path, data.get("info"))
                return None
            return data
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("Amap request failed for %s: %s", path, exc)
            return None
