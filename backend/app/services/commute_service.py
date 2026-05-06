"""Commute evidence service — derives travel time from project config + candidate location.

Persistence: results are cached in ``candidate_commute_evidence`` keyed by a
config-signature hash. The signature mixes project commute config with
candidate location signals; any change to either invalidates on next read. The
project update endpoint also eager-deletes affected rows so a stale row never
even loads. ``not_configured`` and ``insufficient_candidate_location`` are
NOT cached — they reflect input gaps the caller may fill in moments later, so
we don't want to freeze them.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.commute_resolver_agent import CommuteResolverAgent
from ..agent.tools.commute_tools import ToolContext
from ..core.config import settings
from ..db.models import CandidateCommuteEvidence, CandidateListing, SearchProject
from ..integrations.als.client import AlsClient
from ..integrations.amap.client import AmapClient
from ..integrations.geocoding.hk_bbox import in_hk as _in_hk
from ..schemas.commute import CommuteEvidence, CommuteRoute, CommuteSegment
from .mtr_station_service import get_mtr_station_service

logger = logging.getLogger(__name__)


_CACHEABLE_STATUSES = {"ready", "failed"}


class CommuteService:
    """Stateless service that produces derived commute evidence per candidate."""

    def __init__(self) -> None:
        self._client: Optional[AmapClient] = None
        if settings.AMAP_API_KEY:
            self._client = AmapClient(settings.AMAP_API_KEY)
        self._als = AlsClient()
        self._resolver_agent: Optional[CommuteResolverAgent] = None

    def _get_resolver_agent(self) -> CommuteResolverAgent:
        """Build the tool-use agent lazily so missing Amap config doesn't block tests."""
        if self._resolver_agent is None:
            self._resolver_agent = CommuteResolverAgent(
                ToolContext(
                    als=self._als,
                    amap_geocode=self._client,
                    amap_poi=self._client,
                    mtr=get_mtr_station_service(),
                )
            )
        return self._resolver_agent

    async def build_for_candidate(
        self,
        project: SearchProject,
        candidate: CandidateListing,
        db: Optional[AsyncSession] = None,
    ) -> CommuteEvidence:
        """Return commute evidence for a single candidate under a project.

        ``db`` is optional — when provided, results are read from / written to
        the ``candidate_commute_evidence`` cache. Without ``db`` the service
        falls back to its original on-demand-compute behaviour, which is what
        the test suite uses.
        """

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

        # 3. Cache lookup
        signature = _compute_config_signature(project, candidate)
        if db is not None:
            cached = await self._read_cache(db, candidate.id, signature)
            if cached is not None:
                return cached

        # 4. Check that map service is available
        if self._client is None:
            evidence = CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Map service not configured (AMAP_API_KEY missing).",
            )
            await self._write_cache(db, candidate.id, signature, evidence)
            return evidence

        # 5. Resolve destination coordinates (cached on project or geocode now)
        dest_coords = await self._get_destination_coords(project)
        if dest_coords is None:
            evidence = CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Could not geocode destination.",
            )
            await self._write_cache(db, candidate.id, signature, evidence)
            return evidence

        # 6. Resolve candidate coordinates. Try the LLM tool-use agent first,
        #    then fall back to the deterministic ALS → Amap geocode → POI ladder.
        candidate_coords: Optional[tuple[float, float]] = None
        resolved_via: Optional[str] = None
        tried: list[str] = []

        if settings.COMMUTE_AGENT_ENABLED:
            agent_facts = self._agent_facts(candidate)
            try:
                result = await self._get_resolver_agent().ainvoke(agent_facts)
            except Exception as exc:
                logger.warning(
                    "Commute: resolver agent raised for candidate %s, falling back: %s",
                    candidate.id, exc,
                )
                result = None
            if result is not None:
                logger.info(
                    "Commute: agent trace candidate=%s steps=%s resolved_via=%s give_up=%s",
                    candidate.id,
                    result.steps_taken,
                    result.resolved_via,
                    result.give_up_reason,
                )
                for obs in result.observations:
                    tried.append(
                        f"agent:{obs.get('tool')}({obs.get('query')})"
                        f"->{'ok' if obs.get('accepted') else obs.get('reason')}"
                    )
                if result.resolved_coords is not None:
                    candidate_coords = result.resolved_coords
                    resolved_via = f"agent:{result.resolved_via}"

        if candidate_coords is None:
            candidate_coords, resolved_via, fallback_tried = await self._deterministic_resolve(
                location_queries
            )
            tried.extend(fallback_tried)

        if candidate_coords is None:
            logger.warning(
                "Commute: all location lookups failed for candidate %s; tried=%s",
                candidate.id, tried,
            )
            # Not cached — the candidate may gain a usable location signal soon.
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

        # 7. Calculate route — apply departure window for transit only
        departure_date, departure_time = _resolve_departure(project)
        route = await self._calculate_route(
            project.commute_mode,
            candidate_coords,
            dest_coords,
            departure_date,
            departure_time,
        )
        if route is None:
            evidence = CommuteEvidence(
                status="failed",
                destination_label=dest_label,
                mode=project.commute_mode,
                confidence_note="Route calculation failed.",
            )
            await self._write_cache(db, candidate.id, signature, evidence)
            return evidence

        # 8. Success
        raw_segments = route.get("segments") or []
        segments = [CommuteSegment(**seg) for seg in raw_segments] or None
        alternatives = _alternatives_from_route(route) or None
        evidence = CommuteEvidence(
            status="ready",
            estimated_minutes=route["duration_minutes"],
            mode=project.commute_mode,
            route_summary=route.get("route_summary"),
            origin_station=route.get("origin_station"),
            destination_station=route.get("destination_station"),
            segments=segments,
            destination_label=dest_label,
            confidence_note=self._confidence_note(candidate),
            alternatives=alternatives,
        )
        await self._write_cache(db, candidate.id, signature, evidence)
        return evidence

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _read_cache(
        self,
        db: AsyncSession,
        candidate_id,
        expected_signature: str,
    ) -> Optional[CommuteEvidence]:
        """Return cached evidence iff a row exists with a matching signature."""
        result = await db.execute(
            select(CandidateCommuteEvidence).where(
                CandidateCommuteEvidence.candidate_id == candidate_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None or row.config_signature != expected_signature:
            return None
        segments = (
            [CommuteSegment(**seg) for seg in row.segments]
            if row.segments
            else None
        )
        alternatives = _alternatives_from_payload(row.alternatives)
        return CommuteEvidence(
            status=row.status,
            estimated_minutes=row.estimated_minutes,
            mode=row.mode,
            route_summary=row.route_summary,
            origin_station=row.origin_station,
            destination_station=row.destination_station,
            segments=segments,
            destination_label=row.destination_label,
            confidence_note=row.confidence_note,
            alternatives=alternatives,
        )

    async def _write_cache(
        self,
        db: Optional[AsyncSession],
        candidate_id,
        signature: str,
        evidence: CommuteEvidence,
    ) -> None:
        """Upsert the evidence row. No-op when db is None or status not cacheable."""
        if db is None or evidence.status not in _CACHEABLE_STATUSES:
            return

        result = await db.execute(
            select(CandidateCommuteEvidence).where(
                CandidateCommuteEvidence.candidate_id == candidate_id
            )
        )
        row = result.scalar_one_or_none()
        segments_payload = (
            [seg.model_dump() for seg in evidence.segments]
            if evidence.segments
            else None
        )
        alternatives_payload = (
            [alt.model_dump() for alt in evidence.alternatives]
            if evidence.alternatives
            else None
        )
        if row is None:
            row = CandidateCommuteEvidence(
                candidate_id=candidate_id,
                config_signature=signature,
                status=evidence.status,
                estimated_minutes=evidence.estimated_minutes,
                mode=evidence.mode,
                route_summary=evidence.route_summary,
                origin_station=evidence.origin_station,
                destination_station=evidence.destination_station,
                segments=segments_payload,
                destination_label=evidence.destination_label,
                confidence_note=evidence.confidence_note,
                alternatives=alternatives_payload,
            )
            db.add(row)
        else:
            row.config_signature = signature
            row.status = evidence.status
            row.estimated_minutes = evidence.estimated_minutes
            row.mode = evidence.mode
            row.route_summary = evidence.route_summary
            row.origin_station = evidence.origin_station
            row.destination_station = evidence.destination_station
            row.segments = segments_payload
            row.destination_label = evidence.destination_label
            row.confidence_note = evidence.confidence_note
            row.alternatives = alternatives_payload
        await db.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _deterministic_resolve(
        self, location_queries: list[str]
    ) -> tuple[Optional[tuple[float, float]], Optional[str], list[str]]:
        """Fallback ladder: ALS → Amap geocode → Amap POI per query, HK-bbox gated."""
        tried: list[str] = []

        async def _try(path: str, query: str, coro) -> Optional[tuple[float, float]]:
            coords = await coro
            if coords is None:
                tried.append(f"{path}({query})->none")
                return None
            if not _in_hk(coords):
                tried.append(f"{path}({query})->out-of-bbox {coords}")
                return None
            tried.append(f"{path}({query})->{coords}")
            return coords

        for query in location_queries:
            coords = await _try("als", query, self._als.geocode(query))
            if coords is not None:
                return coords, f"ALS '{query}'", tried
            coords = await _try("geocode", query, self._client.geocode(query))
            if coords is not None:
                return coords, f"geocode '{query}'", tried
            coords = await _try("poi", query, self._client.search_poi(query))
            if coords is not None:
                return coords, f"POI '{query}'", tried
        return None, None, tried

    @staticmethod
    def _agent_facts(candidate: CandidateListing) -> dict:
        """Shape the candidate's location signals for the resolver agent prompt."""
        ei = candidate.extracted_info
        if ei is None:
            return {}
        return {
            "address_text": ei.address_text or None,
            "building_name": ei.building_name or None,
            "nearest_station": ei.nearest_station or None,
            "district": ei.district or None,
        }

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
        """Use cached lat/lng when available; otherwise geocode the destination query.

        Same ALS → Amap geocode → Amap POI ladder as the candidate side. Every
        returned coord goes through the HK bbox check — including cached values,
        since rows written before the ALS integration may hold non-HK points.
        """
        if project.commute_destination_lat is not None and project.commute_destination_lng is not None:
            cached = (project.commute_destination_lng, project.commute_destination_lat)
            if _in_hk(cached):
                return cached
            logger.warning(
                "Commute: cached destination coords out of HK bbox for project %s (%s); re-geocoding",
                project.id, cached,
            )
        query = project.commute_destination_query
        for path, coro in (
            ("als", self._als.geocode(query)),
            ("geocode", self._client.geocode(query)),
            ("poi", self._client.search_poi(query)),
        ):
            coords = await coro
            if coords is None:
                continue
            if not _in_hk(coords):
                logger.warning(
                    "Commute: destination %s(%r) out of HK bbox: %s",
                    path, query, coords,
                )
                continue
            return coords
        return None

    async def _calculate_route(
        self,
        mode: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure_date: Optional[str] = None,
        departure_time: Optional[str] = None,
    ) -> Optional[dict]:
        origin_str = f"{origin[0]},{origin[1]}"
        dest_str = f"{destination[0]},{destination[1]}"
        if mode == "transit":
            return await self._client.route_transit(
                origin_str, dest_str, date=departure_date, time=departure_time
            )
        if mode == "driving":
            # Amap driving doesn't take a meaningful time-of-day param; stay "now".
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


# ----------------------------------------------------------------------
# Module-level helpers — pure functions, easy to unit-test without DB.
# ----------------------------------------------------------------------


def _compute_config_signature(project: SearchProject, candidate: CandidateListing) -> str:
    """Stable hash over the inputs that determine a commute estimate.

    Note: the *resolved* departure datetime is intentionally NOT in the
    signature. Two reads of "peak_morning" on different days return the same
    cached estimate — Amap's transit pattern at 08:30 weekday is stable enough
    that paying for a recompute every midnight is not worth it. If the user
    wants a fresh take they can flip to a different window or back.
    """
    ei = candidate.extracted_info
    parts = [
        project.commute_destination_query or "",
        project.commute_mode or "",
        project.commute_departure_window or "now",
        project.commute_departure_time or "",
        f"{project.commute_destination_lat or ''}",
        f"{project.commute_destination_lng or ''}",
        ei.address_text if ei else "",
        ei.building_name if ei else "",
        ei.nearest_station if ei else "",
        ei.district if ei else "",
    ]
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _resolve_departure(project: SearchProject) -> tuple[Optional[str], Optional[str]]:
    """Translate the project's departure window into Amap-shaped (date, time).

    ``now`` returns ``(None, None)`` so Amap defaults to live planning. The
    other windows resolve to the *next* weekday matching the requested HH:MM,
    skipping Sat/Sun — HK transit patterns are weekday-based.
    """
    window = (project.commute_departure_window or "now").lower()
    if window == "now":
        return None, None

    if window == "peak_morning":
        target = _next_weekday_at(8, 30)
    elif window == "peak_evening":
        target = _next_weekday_at(18, 30)
    elif window == "custom":
        custom = project.commute_departure_time
        if not custom or len(custom) != 5 or custom[2] != ":":
            return None, None
        try:
            hh = int(custom[:2])
            mm = int(custom[3:])
        except ValueError:
            return None, None
        target = _next_weekday_at(hh, mm)
    else:
        return None, None

    return target.strftime("%Y-%m-%d"), target.strftime("%H:%M")


def _next_weekday_at(hour: int, minute: int) -> datetime:
    """Next Mon–Fri datetime at the requested HH:MM, strictly in the future."""
    now = datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    while candidate.weekday() >= 5:  # 5 = Sat, 6 = Sun
        candidate = candidate + timedelta(days=1)
    return candidate


def _alternatives_from_route(route: dict) -> list[CommuteRoute]:
    """Convert the Amap-shaped ``alternatives`` list into Pydantic models.

    Amap dicts use ``duration_minutes``; CommuteRoute uses ``estimated_minutes``
    so the cached representation matches the wire schema.
    """
    raw = route.get("alternatives") or []
    out: list[CommuteRoute] = []
    for alt in raw:
        seg_list = (
            [CommuteSegment(**seg) for seg in alt.get("segments") or []] or None
        )
        out.append(
            CommuteRoute(
                label=alt.get("label"),
                estimated_minutes=alt.get("duration_minutes"),
                route_summary=alt.get("route_summary"),
                origin_station=alt.get("origin_station"),
                destination_station=alt.get("destination_station"),
                segments=seg_list,
            )
        )
    return out


def _alternatives_from_payload(payload) -> Optional[list[CommuteRoute]]:
    """Inverse of ``[alt.model_dump() for alt in evidence.alternatives]``."""
    if not payload:
        return None
    out: list[CommuteRoute] = []
    for alt in payload:
        seg_list = (
            [CommuteSegment(**seg) for seg in alt.get("segments") or []] or None
        )
        out.append(
            CommuteRoute(
                label=alt.get("label"),
                estimated_minutes=alt.get("estimated_minutes"),
                route_summary=alt.get("route_summary"),
                origin_station=alt.get("origin_station"),
                destination_station=alt.get("destination_station"),
                segments=seg_list,
            )
        )
    return out
