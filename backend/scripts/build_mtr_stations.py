"""Validate the hand-curated MTR station table against Amap POI.

``backend/app/data/mtr_stations.json`` is checked in — station coords are
platform-level, not shopping-mall-level, so routing won't snap to the
adjacent station. This script re-queries each station through the Amap POI
endpoint and reports drift, optionally writing back corrected coordinates.

Run::

    cd backend
    AMAP_API_KEY=... python -m scripts.build_mtr_stations          # dry-run, report only
    AMAP_API_KEY=... python -m scripts.build_mtr_stations --write  # update coords in place

Idempotent. Never destructive without ``--write``. Skips stations where the
Amap result is > ``_HARD_DRIFT_KM`` away from the hand-curated coord — that
usually means Amap matched a different POI (mall / exit) and we should
fix the alias rather than trust the API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path

# Allow `python -m scripts.build_mtr_stations` when run from backend/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PATH = REPO_ROOT / "app" / "data" / "mtr_stations.json"

_SOFT_DRIFT_M = 150.0   # Report but accept as within station bounds
_HARD_DRIFT_M = 400.0   # Refuse to write — likely wrong POI matched


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371008.8
    lng1, lat1 = math.radians(a[0]), math.radians(a[1])
    lng2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlng = lng2 - lng1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


async def _probe_station(client, station: dict) -> tuple[str, float, tuple[float, float] | None]:
    """Return (status, drift_m, new_coords). status ∈ {ok, drift, hard_drift, miss, error}."""
    # Prefer the traditional Chinese name + "港鐵站" to bias Amap toward the
    # platform POI over shopping centres with the same root name.
    queries = [
        f"{station['name_zh']}港鐵站",
        f"{station['name_zh']}站",
        f"{station['name_en']} MTR Station",
    ]
    hand = (station["lng"], station["lat"])
    for q in queries:
        try:
            coords = await client.search_poi(q)
        except Exception as exc:  # pragma: no cover
            return "error", 0.0, None
        if coords is None:
            continue
        drift = _haversine_m(hand, coords)
        if drift <= _SOFT_DRIFT_M:
            return "ok", drift, coords
        if drift <= _HARD_DRIFT_M:
            return "drift", drift, coords
        # Hard drift: Amap probably matched a different POI. Try next query.
        continue
    return "miss", 0.0, None


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MTR station coords against Amap POI.")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Overwrite coords with Amap results when drift ∈ (soft, hard]. Default: dry-run.",
    )
    args = parser.parse_args(argv)

    api_key = os.getenv("AMAP_API_KEY")
    if not api_key:
        print("AMAP_API_KEY not set — cannot probe Amap POI endpoint.", file=sys.stderr)
        return 2

    from app.integrations.amap.client import AmapClient

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    stations = payload.get("stations") or []
    print(f"validating {len(stations)} stations against Amap POI ...")

    client = AmapClient(api_key)
    updates: list[dict] = []
    ok_count = drift_count = miss_count = hard_count = 0

    for station in stations:
        status, drift_m, new_coords = await _probe_station(client, station)
        if status == "ok":
            ok_count += 1
        elif status == "drift":
            drift_count += 1
            print(
                f"  DRIFT {drift_m:.0f}m  {station['id']:>22}  "
                f"hand=({station['lng']:.5f},{station['lat']:.5f})  "
                f"amap=({new_coords[0]:.5f},{new_coords[1]:.5f})"
            )
            if args.write and new_coords is not None:
                station["lng"] = round(new_coords[0], 5)
                station["lat"] = round(new_coords[1], 5)
                updates.append({"id": station["id"], "drift_m": drift_m})
        elif status == "miss":
            miss_count += 1
            print(f"  MISS  (no HK POI match)  {station['id']}")
        else:
            hard_count += 1
            print(f"  HARD DRIFT (> {_HARD_DRIFT_M:.0f}m)  {station['id']} — check manually")

    print(
        f"\nsummary: {ok_count} ok, {drift_count} drift, "
        f"{miss_count} miss, {hard_count} hard-drift"
    )

    if args.write and updates:
        args.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(updates)} coordinate corrections to {args.path}")
    elif args.write:
        print("no corrections to write")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
