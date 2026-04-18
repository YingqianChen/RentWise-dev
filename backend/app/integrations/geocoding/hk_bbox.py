"""Hong Kong lat/lng bounding box gate.

RentWise is HK-only. This module centralises the envelope so every geocoder
path (ALS, Amap geocode, Amap POI, cached project coords) funnels through the
same check — historical data and upstream bugs both leak PRC points otherwise.
"""

from __future__ import annotations

from typing import Optional

# min_lng, min_lat, max_lng, max_lat — HK SAR envelope with a small buffer.
HK_BBOX = (113.80, 22.15, 114.45, 22.56)


def in_hk(coords: Optional[tuple[float, float]]) -> bool:
    """Return True when *coords* (lng, lat) fall inside the HK bbox."""
    if coords is None:
        return False
    lng, lat = coords
    min_lng, min_lat, max_lng, max_lat = HK_BBOX
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat
