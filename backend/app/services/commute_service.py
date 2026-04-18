"""Commute evidence service — derives travel time from project config + candidate location."""

from __future__ import annotations

import logging
from typing import Optional

from ..core.config import settings
from ..db.models import CandidateListing, SearchProject
from ..integrations.amap.client import AmapClient
from ..schemas.commute import CommuteEvidence

logger = logging.getLogger(__name__)


class CommuteService:
    """Stateless service that produces derived commute evidence per candidate."""

    def __init__(self) -> None:
        self._client: Optional[AmapClient] = None
        if settings.AMAP_API_KEY:
            self._client = AmapClient(settings.AMAP_API_KEY)

    async def build_for_candidate(
        self,
        project: SearchProject,
        candidate: CandidateListing,
    ) -> CommuteEvidence:
        """Return commute evidence for a single candidate under a project."""

        # 1. Check project commute configuration
        if (
            not project.commute_enabled
            or not project.commute_destination_query
            or not project.commute_mode
        ):
            return CommuteEvidence(status="not_configured")

        dest_label = project.commute_destination_label or project.commute_destination_query

        # 2. Collect all candidate location texts
        location_queries = self._location_queries(candidate)
        if not location_queries:
            return CommuteEvidence(
                status="insufficient_candidate_location",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="No address, building name, or nearest station available.",
            )

        # 3. Check that map service is available
        if self._client is None:
            return CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Map service not configured (AMAP_API_KEY missing).",
            )

        # 4. Resolve destination coordinates (cached on project or geocode now)
        dest_coords = await self._get_destination_coords(project)
        if dest_coords is None:
            return CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Could not geocode destination.",
            )

        # 5. Resolve candidate coordinates. Amap's /geocode is weak on English HK
        #    place names (e.g. "Sha Tin MTR", "City One Shatin"); fall back to POI
        #    text search (/place/text) which handles stations and buildings much
        #    better. Try both for each query before moving on.
        candidate_coords = None
        resolved_via: Optional[str] = None
        tried: list[str] = []
        for query in location_queries:
            coords = await self._client.geocode(query)
            tried.append(f"geocode({query})")
            if coords is not None:
                candidate_coords = coords
                resolved_via = f"geocode '{query}'"
                break
            coords = await self._client.search_poi(query)
            tried.append(f"poi({query})")
            if coords is not None:
                candidate_coords = coords
                resolved_via = f"POI '{query}'"
                break
        if candidate_coords is None:
            logger.warning(
                "Commute: all location lookups failed for candidate %s; tried=%s",
                candidate.id, tried,
            )
            return CommuteEvidence(
                status="insufficient_candidate_location",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note=(
                    "Could not resolve a Hong Kong location from the candidate. Tried: "
                    + ", ".join(location_queries)
                    + "."
                ),
            )
        logger.info("Commute: resolved candidate %s via %s", candidate.id, resolved_via)

        # 6. Calculate route
        route = await self._calculate_route(project.commute_mode, candidate_coords, dest_coords)
        if route is None:
            return CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Route calculation failed.",
            )

        # 7. Success
        return CommuteEvidence(
            status="ready",
            estimated_minutes=route["duration_minutes"],
            mode=project.commute_mode,
            route_summary=route.get("route_summary"),
            destination_label=dest_label,
            confidence_note=self._confidence_note(candidate),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _location_queries(candidate: CandidateListing) -> list[str]:
        """Return all usable location texts, most specific first.

        Order: full address > building name > nearest station > district.
        District is a last-ditch fallback — the resulting commute estimate will be
        rough but at least directional.
        """
        ei = candidate.extracted_info
        if ei is None:
            return []
        return [
            value
            for value in (ei.address_text, ei.building_name, ei.nearest_station, ei.district)
            if value and value.lower() not in ("unknown", "")
        ]

    async def _get_destination_coords(
        self, project: SearchProject
    ) -> Optional[tuple[float, float]]:
        """Use cached lat/lng when available; otherwise geocode the destination query."""
        if project.commute_destination_lat is not None and project.commute_destination_lng is not None:
            return (project.commute_destination_lng, project.commute_destination_lat)
        return await self._client.geocode(project.commute_destination_query)

    async def _calculate_route(
        self,
        mode: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> Optional[dict]:
        origin_str = f"{origin[0]},{origin[1]}"
        dest_str = f"{destination[0]},{destination[1]}"
        if mode == "transit":
            return await self._client.route_transit(origin_str, dest_str)
        if mode == "driving":
            return await self._client.route_driving(origin_str, dest_str)
        if mode == "walking":
            return await self._client.route_walking(origin_str, dest_str)
        return None

    @staticmethod
    def _confidence_note(candidate: CandidateListing) -> Optional[str]:
        ei = candidate.extracted_info
        if ei is None:
            return None
        if ei.location_confidence == "high":
            return None
        if ei.location_confidence == "medium":
            return "Location is approximate. Actual commute may differ."
        return "Location is rough. Treat this estimate as directional only."
