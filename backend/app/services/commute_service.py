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

        # 2. Pick the best available candidate location text
        location_query = self._best_location_query(candidate)
        if location_query is None:
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

        # 5. Geocode candidate location
        candidate_coords = await self._client.geocode(location_query)
        if candidate_coords is None:
            return CommuteEvidence(
                status="insufficient_candidate_location",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note=f"Could not geocode candidate location: {location_query!r}.",
            )

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
    def _best_location_query(candidate: CandidateListing) -> Optional[str]:
        """Pick the most specific location text: address > building > station."""
        ei = candidate.extracted_info
        if ei is None:
            return None
        for value in (ei.address_text, ei.building_name, ei.nearest_station):
            if value and value.lower() not in ("unknown", ""):
                return value
        return None

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
