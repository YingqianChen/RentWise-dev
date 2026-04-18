"""Async client for the HK government Address Lookup Service (ALS).

ALS (https://www.als.gov.hk) is the authoritative geocoder for Hong Kong
addresses, estates, buildings, and MTR stations. Unlike Amap it handles
English HK queries (e.g. "Sha Tin MTR station", "City One Shatin") very
well, and it is free, public, and requires no API key. Used as the primary
geocoder with Amap as fallback; Amap still does route planning.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://www.als.gov.hk"
_TIMEOUT = 10.0
# ValidationInformation.Score is 0–100. Empirically, results ≥ 40 are in the
# right district; below that the match is usually a wrong city or unrelated
# building. Tune here, not in callers.
_MIN_SCORE = 40.0


class AlsClient:
    """HK ALS client — `geocode(query)` → ``(longitude, latitude)`` or ``None``."""

    async def geocode(self, query: str) -> Optional[tuple[float, float]]:
        params = {"q": query, "n": 3}
        headers = {"Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{_BASE}/lookup", params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ALS request failed for %r: %s", query, exc)
            return None

        suggestions = data.get("SuggestedAddress") or []
        if not suggestions:
            logger.warning("ALS: no results for %r", query)
            return None

        for item in suggestions:
            score = self._score(item)
            if score < _MIN_SCORE:
                continue
            coords = self._coords(item)
            if coords is not None:
                logger.info("ALS: resolved %r (score=%.1f)", query, score)
                return coords

        top_score = self._score(suggestions[0])
        logger.warning("ALS: no confident HK match for %r (top score=%.1f)", query, top_score)
        return None

    @staticmethod
    def _score(item: dict) -> float:
        try:
            return float((item.get("ValidationInformation") or {}).get("Score", 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _coords(item: dict) -> Optional[tuple[float, float]]:
        geo = (
            ((item.get("Address") or {}).get("PremisesAddress") or {})
            .get("GeospatialInformation")
            or {}
        )
        try:
            lat = float(geo["Latitude"])
            lng = float(geo["Longitude"])
        except (KeyError, ValueError, TypeError):
            return None
        return lng, lat
