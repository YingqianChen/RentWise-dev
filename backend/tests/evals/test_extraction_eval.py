"""End-to-end extraction eval against golden listings.

Skipped by default; run with::

    GROQ_API_KEY=... pytest -m eval backend/tests/evals/test_extraction_eval.py -q

Threshold logic — see ``tests/evals/README.md``.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

if not os.getenv("GROQ_API_KEY"):
    pytest.skip("GROQ_API_KEY not set; eval suite skipped", allow_module_level=True)

from app.db.models import CandidateListing  # noqa: E402
from app.services.extraction_service import ExtractionService  # noqa: E402

from .scoring import CaseResult, FieldResult, aggregate_report, fuzzy_field_match  # noqa: E402

# Per-field pass-rate floors. Start generous and tighten as quality improves.
_FLOORS = {
    "monthly_rent": 0.70,
    "district": 0.70,
    "deposit": 0.50,
    "nearest_station": 0.50,
    "furnished": 0.50,
    "lease_term": 0.50,
}
_OVERALL_FLOOR = 0.55

pytestmark = pytest.mark.eval


def _build_candidate(raw: str) -> CandidateListing:
    now = datetime.now(timezone.utc)
    return CandidateListing(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="eval candidate",
        source_type="manual_text",
        raw_listing_text=raw,
        raw_chat_text=None,
        raw_note_text=None,
        combined_text=raw,
        status="new",
        processing_stage=None,
        processing_error=None,
        user_decision="undecided",
        created_at=now,
        updated_at=now,
    )


async def test_extraction_golden_set(golden_listings, eval_report_writer):
    if not golden_listings:
        pytest.skip("no golden_listings.jsonl samples loaded")

    service = ExtractionService()
    results: list[CaseResult] = []

    for sample in golden_listings:
        candidate = _build_candidate(sample["raw_listing_text"])
        info = await service.extract(candidate)
        expected = sample.get("expected", {})

        field_results: list[FieldResult] = []
        for field_name, expected_value in expected.items():
            actual = getattr(info, field_name, None)
            passed = fuzzy_field_match(expected_value, actual)
            field_results.append(
                FieldResult(field=field_name, passed=passed, expected=expected_value, actual=actual)
            )
        results.append(CaseResult(case_id=sample["id"], fields=field_results))

    report = aggregate_report(results)
    eval_report_writer("extraction_last_run.json", report)

    per_field = report["per_field"]
    violations: list[str] = []
    for field_name, floor in _FLOORS.items():
        if field_name not in per_field:
            continue
        rate = per_field[field_name]["pass_rate"]
        if rate < floor:
            violations.append(f"{field_name}: {rate:.2f} < floor {floor:.2f}")
    if report["overall_pass_rate"] < _OVERALL_FLOOR:
        violations.append(
            f"overall: {report['overall_pass_rate']:.2f} < floor {_OVERALL_FLOOR:.2f}"
        )

    assert not violations, "eval regressions:\n" + "\n".join(violations)
