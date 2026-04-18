"""Async client for Amap (高德地图) REST API — geocoding and route planning."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://restapi.amap.com"
_TIMEOUT = 10.0

# Hong Kong administrative codes all start with "810" (810000 HK SAR, 810001 中西区, ...)
_HK_ADCODE_PREFIX = "810"

# Map Amap busline "type" strings to our compact mode enum.
_MODE_BY_BUSLINE_TYPE = {
    "地铁线路": "subway",
    "地铁": "subway",
    "机场快线": "airport_express",
    "城际铁路": "rail",
    "普通铁路": "rail",
    "专线小巴": "minibus",
    "小巴": "minibus",
}


def _busline_mode(busline_type: str) -> str:
    return _MODE_BY_BUSLINE_TYPE.get(busline_type or "", "bus")


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_transit_segments(raw_segments: list) -> list[dict]:
    """Flatten Amap transit segments into ordered legs.

    Each raw segment can contain ``walking``, ``bus`` (with ``buslines[]``),
    ``railway``, and/or ``taxi``. We emit one leg per mode present, preserving
    order within the segment. Empty walking stubs (0s / <=10m) are dropped —
    Amap likes to pad routes with them.
    """
    legs: list[dict] = []
    for seg in raw_segments:
        walking = seg.get("walking") or {}
        walk_sec = _to_int(walking.get("duration"))
        walk_m = _to_int(walking.get("distance"))
        if walk_sec > 0 or walk_m > 10:
            legs.append({
                "mode": "walking",
                "line_name": None,
                "from_station": None,
                "to_station": None,
                "duration_minutes": max(1, round(walk_sec / 60)) if walk_sec else None,
                "distance_meters": walk_m or None,
            })

        bus = seg.get("bus") or {}
        for busline in (bus.get("buslines") or [])[:1]:  # take the first option per segment
            bl_type = busline.get("type") or ""
            bl_sec = _to_int(busline.get("duration"))
            legs.append({
                "mode": _busline_mode(bl_type),
                "line_name": busline.get("name") or None,
                "from_station": (busline.get("departure_stop") or {}).get("name") or None,
                "to_station": (busline.get("arrival_stop") or {}).get("name") or None,
                "duration_minutes": max(1, round(bl_sec / 60)) if bl_sec else None,
                "distance_meters": _to_int(busline.get("distance")) or None,
            })

        railway = seg.get("railway") or {}
        if railway.get("name"):
            rw_sec = _to_int(railway.get("time"))
            legs.append({
                "mode": "rail",
                "line_name": railway.get("name"),
                "from_station": (railway.get("departure_stop") or {}).get("name") or None,
                "to_station": (railway.get("arrival_stop") or {}).get("name") or None,
                "duration_minutes": max(1, round(rw_sec / 60)) if rw_sec else None,
                "distance_meters": _to_int(railway.get("distance")) or None,
            })

        taxi = seg.get("taxi") or {}
        if _to_int(taxi.get("distance")) > 0:
            tx_sec = _to_int(taxi.get("drivetime"))
            legs.append({
                "mode": "taxi",
                "line_name": None,
                "from_station": taxi.get("sname") or None,
                "to_station": taxi.get("tname") or None,
                "duration_minutes": max(1, round(tx_sec / 60)) if tx_sec else None,
                "distance_meters": _to_int(taxi.get("distance")) or None,
            })
    return legs


def _endpoints(legs: list[dict]) -> tuple[Optional[str], Optional[str]]:
    non_walking = [leg for leg in legs if leg["mode"] != "walking"]
    if not non_walking:
        return None, None
    return non_walking[0].get("from_station"), non_walking[-1].get("to_station")


def _summary_from_legs(legs: list[dict]) -> Optional[str]:
    parts: list[str] = []
    for leg in legs:
        mode = leg["mode"]
        if mode == "walking":
            mins = leg.get("duration_minutes")
            parts.append(f"步行{mins}分钟" if mins else "步行")
            continue
        line = leg.get("line_name") or ""
        dest = leg.get("to_station") or ""
        if line and dest:
            parts.append(f"{line} → {dest}")
        elif line:
            parts.append(line)
        elif dest:
            parts.append(dest)
    return " · ".join(parts) if parts else None


class AmapClient:
    """Thin async wrapper around Amap Web Service API endpoints."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    async def geocode(self, address: str, city: str = "香港") -> Optional[tuple[float, float]]:
        """Geocode *address* → ``(longitude, latitude)`` or *None*.

        Tries progressively stronger Hong Kong hints so English place names
        have more chances to resolve inside the HK admin region.
        """
        result = await self._geocode_once(address, city)
        if result is not None:
            return result
        if "香港" not in address and "Hong Kong" not in address:
            result = await self._geocode_once(f"{address} 香港", city)
            if result is not None:
                return result
        if "特别行政区" not in address:
            return await self._geocode_once(f"{address} 香港特别行政区", city)
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
        top = geocodes[0]
        adcode = str(top.get("adcode") or "")
        if not adcode.startswith(_HK_ADCODE_PREFIX):
            logger.warning(
                "Amap geocode returned non-HK result for %r (adcode=%s, city=%s)",
                address, adcode, top.get("city"),
            )
            return None
        location = top.get("location", "")
        try:
            lng, lat = location.split(",")
            return float(lng), float(lat)
        except (ValueError, AttributeError):
            logger.warning("Amap geocode: bad location format %r", location)
            return None

    # ------------------------------------------------------------------
    # POI text search (better fit for MTR stations, buildings, landmarks)
    # ------------------------------------------------------------------

    async def search_poi(self, keywords: str, city: str = "香港") -> Optional[tuple[float, float]]:
        """Place-text POI search → ``(longitude, latitude)`` of top HK result or *None*.

        Amap geocoding (``/v3/geocode/geo``) handles street addresses. MTR stations,
        building names, and landmarks are POIs and resolve much better through
        ``/v3/place/text``. Used as a fallback when geocoding fails.
        """
        params = {
            "key": self._api_key,
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "offset": 5,
            "page": 1,
        }
        data = await self._get("/v3/place/text", params)
        if data is None:
            return None
        pois = data.get("pois") or []
        if not pois:
            logger.warning("Amap POI search returned no results for %r", keywords)
            return None
        for poi in pois:
            adcode = str(poi.get("adcode") or "")
            if not adcode.startswith(_HK_ADCODE_PREFIX):
                continue
            location = poi.get("location", "")
            try:
                lng, lat = location.split(",")
                return float(lng), float(lat)
            except (ValueError, AttributeError):
                continue
        logger.warning(
            "Amap POI search: no HK results for %r (top adcode=%s)",
            keywords, pois[0].get("adcode"),
        )
        return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def route_transit(
        self, origin: str, destination: str, city: str = "香港"
    ) -> Optional[dict]:
        """Transit routing → structured legs or *None*.

        Return shape::

            {
                "duration_minutes": int,
                "origin_station": str | None,
                "destination_station": str | None,
                "segments": [CommuteSegment-shaped dicts...],
                "route_summary": str | None,
            }
        """
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
        legs = _parse_transit_segments(best.get("segments") or [])
        origin_station, destination_station = _endpoints(legs)
        return {
            "duration_minutes": max(1, round(duration_sec / 60)),
            "origin_station": origin_station,
            "destination_station": destination_station,
            "segments": legs,
            "route_summary": _summary_from_legs(legs),
        }

    async def route_driving(self, origin: str, destination: str) -> Optional[dict]:
        """Driving routing → duration + empty legs (schema parity)."""
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
        return {
            "duration_minutes": max(1, round(duration_sec / 60)),
            "origin_station": None,
            "destination_station": None,
            "segments": [],
            "route_summary": None,
        }

    async def route_walking(self, origin: str, destination: str) -> Optional[dict]:
        """Walking routing → duration + single walking leg."""
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
            distance_m = int(best.get("distance", 0))
        except (TypeError, ValueError):
            duration_sec, distance_m = 0, 0
        duration_min = max(1, round(duration_sec / 60))
        leg = {
            "mode": "walking",
            "line_name": None,
            "from_station": None,
            "to_station": None,
            "duration_minutes": duration_min,
            "distance_meters": distance_m or None,
        }
        return {
            "duration_minutes": duration_min,
            "origin_station": None,
            "destination_station": None,
            "segments": [leg],
            "route_summary": None,
        }

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
