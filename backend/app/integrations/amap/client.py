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


def _parse_one_transit(transit: dict) -> dict:
    """Convert one Amap ``transits[]`` entry into the route dict shape."""
    try:
        duration_sec = int(transit.get("duration", 0))
    except (TypeError, ValueError):
        duration_sec = 0
    legs = _parse_transit_segments(transit.get("segments") or [])
    origin_station, destination_station = _endpoints(legs)
    return {
        "duration_minutes": max(1, round(duration_sec / 60)) if duration_sec else 1,
        "origin_station": origin_station,
        "destination_station": destination_station,
        "segments": legs,
        "route_summary": _summary_from_legs(legs),
    }


def _route_signature(route: dict) -> str:
    """Stable identity for dedup — same primary modes + endpoints = same route.

    We don't use ``route_summary`` directly because Amap often varies walking
    minutes by 1 across near-duplicates while the actual ride is identical.
    Comparing only the non-walking line names + endpoints catches that.
    """
    line_keys: list[str] = []
    for leg in route.get("segments") or []:
        if leg.get("mode") == "walking":
            continue
        line_keys.append(
            f"{leg.get('mode','')}|{leg.get('line_name','')}|"
            f"{leg.get('from_station','')}|{leg.get('to_station','')}"
        )
    return "::".join(line_keys) or (route.get("route_summary") or "")


def _non_walking_count(route: dict) -> int:
    return sum(
        1 for leg in (route.get("segments") or []) if leg.get("mode") != "walking"
    )


def _walking_meters(route: dict) -> int:
    return sum(
        int(leg.get("distance_meters") or 0)
        for leg in (route.get("segments") or [])
        if leg.get("mode") == "walking"
    )


def _select_primary_and_alternatives(routes: list[dict]) -> tuple[dict, list[dict]]:
    """Pick the fastest as primary; label up to 2 distinct alternates.

    Alternative labels:
        - "Fewer transfers" — non-primary route with fewest non-walking legs
          (only shown if strictly fewer than primary's count)
        - "Less walking" — non-primary route with smallest total walking
          distance (only shown if strictly less than primary's walking)

    If both labels point at the same route, only one is shown. If neither
    label applies (all routes share primary's structure), alternatives is
    empty.
    """
    if not routes:
        raise ValueError("routes must be non-empty")

    # Dedupe while preserving the first occurrence's order.
    seen: set[str] = set()
    distinct: list[dict] = []
    for route in routes:
        sig = _route_signature(route)
        if sig in seen:
            continue
        seen.add(sig)
        distinct.append(route)

    by_duration = sorted(distinct, key=lambda r: r["duration_minutes"])
    primary = by_duration[0]
    pool = [r for r in distinct if r is not primary]
    alternatives: list[dict] = []
    used_sigs: set[str] = {_route_signature(primary)}

    primary_transfers = _non_walking_count(primary)
    fewer_transfer_pool = [r for r in pool if _non_walking_count(r) < primary_transfers]
    if fewer_transfer_pool:
        # Among routes with fewer transfers, pick the fastest.
        choice = sorted(
            fewer_transfer_pool,
            key=lambda r: (_non_walking_count(r), r["duration_minutes"]),
        )[0]
        sig = _route_signature(choice)
        if sig not in used_sigs:
            alt = dict(choice)
            alt["label"] = "Fewer transfers"
            alternatives.append(alt)
            used_sigs.add(sig)

    primary_walk = _walking_meters(primary)
    less_walking_pool = [r for r in pool if _walking_meters(r) < primary_walk]
    if less_walking_pool:
        choice = sorted(
            less_walking_pool,
            key=lambda r: (_walking_meters(r), r["duration_minutes"]),
        )[0]
        sig = _route_signature(choice)
        if sig not in used_sigs:
            alt = dict(choice)
            alt["label"] = "Less walking"
            alternatives.append(alt)
            used_sigs.add(sig)

    # If we still have room and there's a structurally-different second route,
    # show it as a generic "Alternative" so the user always sees more than one
    # option when one exists.
    if not alternatives and len(distinct) >= 2:
        choice = by_duration[1]
        alt = dict(choice)
        alt["label"] = "Alternative"
        alternatives.append(alt)

    return primary, alternatives


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
        self,
        origin: str,
        destination: str,
        city: str = "香港",
        date: Optional[str] = None,
        time: Optional[str] = None,
    ) -> Optional[dict]:
        """Transit routing → primary route + labeled alternatives, or *None*.

        ``date`` (``YYYY-MM-DD``) and ``time`` (``HH:MM``) are forwarded to
        Amap as the planned departure. Both must be provided together — Amap
        ignores either alone. Without them the API plans for "now".

        Return shape — primary route is at the top level (so callers ignoring
        ``alternatives`` see only the best option as before)::

            {
                "duration_minutes": int,
                "origin_station": str | None,
                "destination_station": str | None,
                "segments": [CommuteSegment-shaped dicts...],
                "route_summary": str | None,
                "alternatives": [  # 0..2 distinct alternates, labeled
                    {
                        "label": "Fewer transfers" | "Less walking" | "Alt",
                        "duration_minutes": int,
                        "origin_station": str | None,
                        "destination_station": str | None,
                        "segments": [...],
                        "route_summary": str | None,
                    },
                    ...
                ],
            }
        """
        params = {
            "key": self._api_key,
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": city,
        }
        if date and time:
            params["date"] = date
            params["time"] = time
        data = await self._get("/v3/direction/transit/integrated", params)
        if data is None:
            return None
        route = data.get("route") or {}
        transits = route.get("transits") or []
        if not transits:
            logger.warning("Amap transit: no routes for %s → %s", origin, destination)
            return None
        parsed = [_parse_one_transit(transit) for transit in transits]
        # Drop empty parses (Amap occasionally returns transits with zero useful legs).
        parsed = [p for p in parsed if p["segments"]]
        if not parsed:
            logger.warning("Amap transit: all transits parsed empty for %s → %s", origin, destination)
            return None
        primary, alternatives = _select_primary_and_alternatives(parsed)
        primary["alternatives"] = alternatives
        return primary

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
