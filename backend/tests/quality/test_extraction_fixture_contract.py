"""Deterministic contract checks for the LLM extraction golden samples."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.candidate_field_registry import CANDIDATE_FIELD_KEYS


_FIXTURES_DIR = Path(__file__).parents[1] / "evals" / "fixtures"
_LISTINGS_PATH = _FIXTURES_DIR / "golden_listings.jsonl"
_REVIEW_PATH = _FIXTURES_DIR / "golden_listings_review.json"
_SUPPORTED_EXPECTED_FIELDS = set(CANDIDATE_FIELD_KEYS) | {
    "furnished",
    "size_sqft",
    "bedrooms",
    "suspected_sdu",
    "sdu_detection_reason",
}
_PHONE_PATTERN = re.compile(r"(?:\+?852[\s-]?)?\d{4}[\s-]?\d{4}")
_CONTACT_PATTERN = re.compile(
    r"\b(?:whatsapp|wechat|phone)\b|(?:電話|電話號碼|手机|手機|聯絡|联系)",
    re.IGNORECASE,
)


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path.name}:{line_no} is not valid JSON: {exc}") from exc
    return rows


def _is_non_empty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(_is_non_empty(item) for item in value)
    return True


def test_golden_listing_fixture_matches_review_contract() -> None:
    listings = _load_jsonl(_LISTINGS_PATH)
    review = json.loads(_REVIEW_PATH.read_text(encoding="utf-8"))

    assert len(listings) == 14
    assert review["dataset"] == "synthetic_hk_rental_v1"
    assert review["review_status"] == "manually_checked"

    ids = [listing.get("id") for listing in listings]
    assert all(isinstance(sample_id, str) and sample_id.strip() for sample_id in ids)
    assert len(ids) == len(set(ids)), "golden listing ids must be unique"
    assert set(ids) == set(review["reviewed_sample_ids"])

    for listing in listings:
        raw_text = listing.get("raw_listing_text")
        assert isinstance(raw_text, str) and raw_text.strip()
        expected = listing.get("expected")
        assert isinstance(expected, dict) and expected
        unsupported = set(expected) - _SUPPORTED_EXPECTED_FIELDS
        assert not unsupported, f"{listing['id']} uses unsupported fields: {sorted(unsupported)}"
        for field_name, expected_value in expected.items():
            assert _is_non_empty(expected_value), (
                f"{listing['id']} {field_name} has an empty expectation"
            )
        assert not _PHONE_PATTERN.search(raw_text), f"{listing['id']} appears to contain a phone number"
        assert not _CONTACT_PATTERN.search(raw_text), (
            f"{listing['id']} appears to contain personal contact details"
        )


@pytest.mark.parametrize(
    "sample_id",
    [
        "kt_chat_01",
        "ym_sdu_01",
        "tw_bilingual_01",
        "ssp_tonglau_01",
        "cwb_serviced_01",
        "tp_conflict_01",
    ],
)
def test_new_samples_are_explicitly_covered(sample_id: str) -> None:
    review = json.loads(_REVIEW_PATH.read_text(encoding="utf-8"))
    covered = {
        sample_id
        for sample_ids in review["coverage"].values()
        for sample_id in sample_ids
    }
    assert sample_id in covered
