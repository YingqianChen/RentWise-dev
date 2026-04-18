"""Retrieval-recall eval for the tenancy ordinance BM25 index.

Unlike the other evals this one doesn't call the LLM — it just checks that
plausible legal queries pull back chunks from plausible pages of
``document/AGuideToTenancy_ch.pdf``. It uses the committed index at
``backend/app/data/tenancy_index.json``; when that file is missing the test
skips (run ``python -m scripts.build_tenancy_index`` to rebuild).

Because it's BM25-only (no network, no keys), this eval runs whenever the
user opts into the eval suite with ``-m eval``, even without GROQ_API_KEY.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.tenancy_rag_service import TenancyRagService

from .scoring import CaseResult, FieldResult, aggregate_report


pytestmark = pytest.mark.eval

_INDEX_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "tenancy_index.json"

# Each case: a query a user / LLM might send, plus the ordinance page ranges we
# expect at least one of the top-3 hits to fall within. Page numbers come from
# ``AGuideToTenancy_ch.pdf`` — verified by hand against the OCR'd output.
_CASES: list[dict] = [
    {"id": "repair_responsibility", "query": "維修 責任 業主 租客", "expected_pages": {12, 15}},
    {"id": "deposit", "query": "押金 二按 退回", "expected_pages": {13, 14, 15}},
    {"id": "lease_term", "query": "租期 生約 死約 提前 終止", "expected_pages": {11, 15}},
    {"id": "move_in_timing", "query": "入住 交樓 日期 起租", "expected_pages": {11, 12, 15}},
    {"id": "agent_role", "query": "地產代理 牌照 責任", "expected_pages": {5, 7, 15}},
    {"id": "discrimination", "query": "歧視 性別 種族 條例", "expected_pages": {5, 8}},
    {"id": "written_agreement", "query": "租約 書面 副本 打釐印", "expected_pages": {11, 13}},
    {"id": "rates_and_management", "query": "差餉 管理費 水電", "expected_pages": {11, 12, 15}},
]


def test_tenancy_rag_top_k_recall(eval_report_writer) -> None:
    if not _INDEX_PATH.exists():
        pytest.skip(
            "tenancy_index.json not built — run `python -m scripts.build_tenancy_index`"
        )

    service = TenancyRagService(index_path=_INDEX_PATH)
    if service.chunk_count == 0:
        pytest.skip("tenancy index contains no chunks")

    results: list[CaseResult] = []
    for case in _CASES:
        hits = service.retrieve(case["query"], k=3)
        hit_pages = {hit.source_page for hit in hits}
        passed = bool(hit_pages & case["expected_pages"])
        results.append(
            CaseResult(
                case_id=case["id"],
                fields=[
                    FieldResult(
                        field="top3_page_hit",
                        passed=passed,
                        expected=sorted(case["expected_pages"]),
                        actual=sorted(hit_pages),
                    )
                ],
            )
        )

    report = aggregate_report(results)
    eval_report_writer("tenancy_rag_last_run.json", report)

    pass_rate = report["per_field"]["top3_page_hit"]["pass_rate"]
    floor = 0.60
    assert pass_rate >= floor, f"tenancy RAG recall {pass_rate:.2f} < floor {floor:.2f}"
