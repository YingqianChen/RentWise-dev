"""Hand-curated MTR station lookup.

Most Hong Kong place names double as a district name (沙田, 湾仔, 观塘, ...),
so ``nearest_station = "Sha Tin"`` is ambiguous: it might mean the station or
the district. Treating the bare string as a station is dangerous — routing
snaps the coord to whatever happens to be nearby, which is how a candidate
literally labelled "Sha Tin MTR station" ended up with an origin reported as
大围 (the adjacent station).

This service accepts lookups **only when the caller included an explicit
station marker** — "MTR", "Station", "站", "地鐵站", "港鐵站", or the simplified
variants. Anything else (bare name, "X District", "X 区") returns ``None`` so
the caller falls back to general geocoding.

Data lives at ``backend/app/data/mtr_stations.json`` — hand-curated, coords
validated via ``python -m scripts.build_mtr_stations``.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "mtr_stations.json"

# Order matters: longer markers must be tried first so "MTR Station" isn't
# partly matched as just "Station" (which would leave an "MTR" suffix).
_STATION_MARKERS_EN = (
    " mtr station",
    " mtr stn",
    " metro station",
    " subway station",
    " station",
    " mtr",
    " stn",
)
_STATION_MARKERS_ZH = (
    "港鐵站",
    "港铁站",
    "地鐵站",
    "地铁站",
    "鐵路站",
    "铁路站",
    "站",
)
# Explicit district / area markers — reject even if the root also happens to
# be a known station name.
_DISTRICT_MARKERS_EN = (" district", " area")
_DISTRICT_MARKERS_ZH = ("區", "区")


@dataclass(frozen=True)
class MtrStation:
    id: str
    name_en: str
    name_zh: str
    lng: float
    lat: float
    line: str


class MtrStationService:
    """Lazy-loaded singleton-friendly lookup over the MTR station table."""

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._by_key: dict[str, MtrStation] = {}
        self._loaded = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning(
                "mtr_stations.json missing at %s — lookups will return None",
                self._path,
            )
            self._loaded = True
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("failed to load mtr_stations.json: %s", exc)
            self._loaded = True
            return

        for raw in payload.get("stations") or []:
            try:
                station = MtrStation(
                    id=raw["id"],
                    name_en=raw["name_en"],
                    name_zh=raw["name_zh"],
                    lng=float(raw["lng"]),
                    lat=float(raw["lat"]),
                    line=raw.get("line") or "",
                )
            except (KeyError, TypeError, ValueError):
                logger.warning("skipping malformed MTR station entry: %r", raw)
                continue
            for key in self._keys_for(station, raw.get("aliases") or []):
                self._by_key[key] = station
        self._loaded = True
        logger.info("loaded %d MTR station lookup keys", len(self._by_key))

    @staticmethod
    def _keys_for(station: MtrStation, aliases: list[str]) -> list[str]:
        """Normalised key variants pointing at this station.

        Only the bare canonical / alias names go in. Callers must supply a
        station marker at lookup time — that marker is stripped before the key
        is compared, so we don't need to pre-pollute the dict with "X Station"
        variants.
        """
        seen: set[str] = set()
        out: list[str] = []
        candidates = [station.name_en, station.name_zh, *aliases]
        for cand in candidates:
            if not cand:
                continue
            key = _normalise_key(cand)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, raw: str) -> Optional[tuple[float, float, str]]:
        """Return ``(lng, lat, canonical_name_en)`` for an unambiguous MTR name.

        Returns ``None`` if:
          * input is empty
          * input carries a district marker (``District`` / ``区``)
          * input has no station marker (bare name is ambiguous with district)
          * the stripped root doesn't match a known station or alias
        """
        self._ensure_loaded()
        if not raw:
            return None
        text = raw.strip()
        if not text:
            return None

        # Explicit district → always reject.
        lower = text.lower()
        for mkr in _DISTRICT_MARKERS_EN:
            if mkr in lower or lower.endswith(mkr.strip()):
                return None
        for mkr in _DISTRICT_MARKERS_ZH:
            if text.endswith(mkr):
                return None

        root = _strip_station_marker(text)
        if root is None:
            # No marker present → ambiguous with district name.
            return None

        key = _normalise_key(root)
        if not key:
            return None

        station = self._by_key.get(key)
        if station is None:
            return None
        return station.lng, station.lat, station.name_en

    @property
    def station_count(self) -> int:
        self._ensure_loaded()
        return len({s.id for s in self._by_key.values()})


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _strip_station_marker(text: str) -> Optional[str]:
    """Return the root with its station marker removed, or ``None`` if absent.

    English markers are matched case-insensitively on a leading space-padded
    form so "MTR" inside "MTR Roma" (hypothetical) doesn't accidentally strip.
    Chinese markers are plain suffixes.
    """
    lowered = " " + text.lower()
    for mkr in _STATION_MARKERS_EN:
        if lowered.endswith(mkr):
            cut = len(mkr) - 1  # subtract the leading space we added
            stripped = text[: len(text) - cut].rstrip(" -")
            return stripped.strip() or None

    for mkr in _STATION_MARKERS_ZH:
        if text.endswith(mkr):
            stripped = text[: len(text) - len(mkr)].rstrip()
            # Handle nested markers, e.g. "沙田地鐵站" → first strips "站",
            # leaves "沙田地鐵" — strip again.
            while True:
                shrunk = False
                for inner in _STATION_MARKERS_ZH:
                    if stripped.endswith(inner):
                        stripped = stripped[: len(stripped) - len(inner)].rstrip()
                        shrunk = True
                        break
                if not shrunk:
                    break
            return stripped or None

    return None


def _normalise_key(text: str) -> str:
    """Collapse whitespace + case for dict keys. Chinese chars untouched."""
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed.lower()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_default_service: Optional[MtrStationService] = None


def get_mtr_station_service() -> MtrStationService:
    global _default_service
    if _default_service is None:
        _default_service = MtrStationService()
    return _default_service
