"""Unit tests for :class:`MtrStationService`.

The service is deliberately strict about ambiguity — most HK MTR station
names double as district / town names, so lookups must require an explicit
station marker. These tests pin that behaviour so a future "oh, let's accept
the bare name" refactor trips immediately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.mtr_station_service import MtrStationService


FIXTURE = {
    "version": 1,
    "stations": [
        {
            "id": "sha_tin",
            "line": "East Rail",
            "name_en": "Sha Tin",
            "name_zh": "沙田",
            "lng": 114.1872,
            "lat": 22.3818,
            "aliases": ["Shatin"],
        },
        {
            "id": "tai_wai",
            "line": "East Rail",
            "name_en": "Tai Wai",
            "name_zh": "大圍",
            "lng": 114.1787,
            "lat": 22.3731,
            "aliases": ["大围"],
        },
        {
            "id": "mong_kok",
            "line": "Tsuen Wan",
            "name_en": "Mong Kok",
            "name_zh": "旺角",
            "lng": 114.1684,
            "lat": 22.3191,
            "aliases": [],
        },
        {
            "id": "mong_kok_east",
            "line": "East Rail",
            "name_en": "Mong Kok East",
            "name_zh": "旺角東",
            "lng": 114.1724,
            "lat": 22.3221,
            "aliases": ["旺角东"],
        },
        {
            "id": "tsuen_wan",
            "line": "Tsuen Wan",
            "name_en": "Tsuen Wan",
            "name_zh": "荃灣",
            "lng": 114.1176,
            "lat": 22.3740,
            "aliases": ["荃湾"],
        },
    ],
}


@pytest.fixture()
def service(tmp_path: Path) -> MtrStationService:
    path = tmp_path / "mtr_stations.json"
    path.write_text(json.dumps(FIXTURE, ensure_ascii=False), encoding="utf-8")
    return MtrStationService(path=path)


# ---------------------------------------------------------------------------
# 1. Explicit station markers → successful match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "Sha Tin MTR Station",
        "Sha Tin Station",
        "Sha Tin MTR",
        "sha tin mtr station",    # case-insensitive
        "SHA TIN STATION",
        "沙田站",
        "沙田地鐵站",
        "沙田地铁站",
        "沙田港鐵站",
        "沙田港铁站",
        "Shatin MTR Station",     # alias
    ],
)
def test_resolves_sha_tin_with_station_marker(service: MtrStationService, query: str) -> None:
    result = service.lookup(query)
    assert result is not None, f"expected hit for {query!r}"
    lng, lat, canonical = result
    assert canonical == "Sha Tin"
    assert round(lng, 4) == 114.1872
    assert round(lat, 4) == 22.3818


# ---------------------------------------------------------------------------
# 2. Bare name → rejected as ambiguous
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "Sha Tin",          # could mean Sha Tin District
        "沙田",              # district or station
        "Mong Kok",         # doubles as 旺角 neighbourhood
        "旺角",
        "Tsuen Wan",
        "荃灣",
        "荃湾",
    ],
)
def test_bare_name_rejected(service: MtrStationService, query: str) -> None:
    assert service.lookup(query) is None


# ---------------------------------------------------------------------------
# 3. District markers → explicitly rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "Sha Tin District",
        "Sha Tin Area",
        "沙田区",
        "沙田區",
        "Mong Kok District",
        "旺角区",
    ],
)
def test_district_marker_rejected(service: MtrStationService, query: str) -> None:
    assert service.lookup(query) is None


# ---------------------------------------------------------------------------
# 4. Traditional / simplified equivalence
# ---------------------------------------------------------------------------


def test_simplified_alias_matches_traditional(service: MtrStationService) -> None:
    """荃灣 (traditional, primary name_zh) and 荃湾 (simplified, alias) both resolve."""
    trad = service.lookup("荃灣站")
    simp = service.lookup("荃湾站")
    assert trad is not None and simp is not None
    assert trad[2] == simp[2] == "Tsuen Wan"


def test_tai_wai_simplified_variant(service: MtrStationService) -> None:
    result = service.lookup("大围站")
    assert result is not None
    assert result[2] == "Tai Wai"


# ---------------------------------------------------------------------------
# 5. Close-but-distinct station names must not cross-match
# ---------------------------------------------------------------------------


def test_mong_kok_east_and_mong_kok_resolve_distinctly(service: MtrStationService) -> None:
    east = service.lookup("Mong Kok East MTR Station")
    west = service.lookup("Mong Kok MTR Station")
    assert east is not None and west is not None
    assert east[2] == "Mong Kok East"
    assert west[2] == "Mong Kok"
    # coords must be distinct
    assert (east[0], east[1]) != (west[0], west[1])


# ---------------------------------------------------------------------------
# 6. Unknown station / empty / None inputs
# ---------------------------------------------------------------------------


def test_unknown_station_returns_none(service: MtrStationService) -> None:
    assert service.lookup("Atlantis Station") is None
    assert service.lookup("火星站") is None


def test_empty_input_returns_none(service: MtrStationService) -> None:
    assert service.lookup("") is None
    assert service.lookup("   ") is None


# ---------------------------------------------------------------------------
# 7. Missing index file → graceful None
# ---------------------------------------------------------------------------


def test_missing_index_file_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    svc = MtrStationService(path=missing)
    assert svc.lookup("Sha Tin MTR Station") is None
    assert svc.station_count == 0


# ---------------------------------------------------------------------------
# 8. Production index file sanity
# ---------------------------------------------------------------------------


def test_production_index_loads() -> None:
    """Make sure the committed data file stays well-formed and findable."""
    svc = MtrStationService()
    # We should see at least a few dozen stations.
    assert svc.station_count >= 80
    # Representative stations must resolve.
    for query, expected_en in [
        ("Sha Tin MTR Station", "Sha Tin"),
        ("Tai Wai MTR Station", "Tai Wai"),
        ("Central Station", "Central"),
        ("Admiralty MTR", "Admiralty"),
        ("沙田站", "Sha Tin"),
        ("大圍站", "Tai Wai"),
        ("旺角东站", "Mong Kok East"),
    ]:
        result = svc.lookup(query)
        assert result is not None, f"production index missing lookup for {query!r}"
        assert result[2] == expected_en
    # Bare district names still get rejected by the production data.
    assert svc.lookup("Sha Tin") is None
    assert svc.lookup("沙田") is None
