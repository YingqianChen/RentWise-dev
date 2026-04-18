"""Unit tests for the tenancy BM25 retrieval service.

These tests build a tiny temporary index on disk — the real ordinance index
lives at ``backend/app/data/tenancy_index.json`` and is exercised by the eval
suite, not here. Unit tests should stay hermetic and fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.tenancy_rag_service import TenancyRagService, _tokenise


def _write_index(path: Path, chunks: list[dict]) -> None:
    payload = {
        "version": 1,
        "source_pdf": "test.pdf",
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _chunk(cid: str, text: str, page: int) -> dict:
    return {"id": cid, "text": text, "source_page": page, "tokens": _tokenise(text)}


def test_retrieve_ranks_keyword_matching_chunk_first(tmp_path: Path) -> None:
    idx = tmp_path / "idx.json"
    _write_index(
        idx,
        [
            _chunk("c_repair", "租客須負責維修單位的耗損。業主則負責結構性維修。", 5),
            _chunk("c_deposit", "押金一般為兩個月租金加一個月上期，俗稱押二上一。", 7),
            _chunk("c_intro", "前言及聲明。本指南供一般參考之用。", 1),
        ],
    )
    service = TenancyRagService(index_path=idx)

    hits = service.retrieve("維修 責任", k=3)

    assert hits, "expected at least one hit"
    assert hits[0].id == "c_repair"
    assert hits[0].source_page == 5


def test_empty_query_returns_empty(tmp_path: Path) -> None:
    idx = tmp_path / "idx.json"
    _write_index(idx, [_chunk("c_a", "任何內容", 1)])
    service = TenancyRagService(index_path=idx)

    assert service.retrieve("", k=3) == []
    assert service.retrieve("   ", k=3) == []


def test_k_is_capped_to_chunk_count(tmp_path: Path) -> None:
    idx = tmp_path / "idx.json"
    _write_index(
        idx,
        [
            _chunk("c_a", "押金 退回 條款", 1),
            _chunk("c_b", "維修 責任 業主", 2),
        ],
    )
    service = TenancyRagService(index_path=idx)

    hits = service.retrieve("押金", k=10)
    assert len(hits) == 2


def test_missing_index_file_returns_empty(tmp_path: Path) -> None:
    idx = tmp_path / "nonexistent.json"
    service = TenancyRagService(index_path=idx)

    assert service.retrieve("維修", k=5) == []
    assert service.chunk_count == 0


@pytest.mark.parametrize(
    "text,expected_subset",
    [
        ("維修 責任", {"維修", "責任"}),
        ("Mong Kok 租客", {"mong", "kok", "租客"}),
        ("   ", set()),
    ],
)
def test_tokeniser_drops_punctuation_and_lowercases(
    text: str, expected_subset: set[str]
) -> None:
    tokens = set(_tokenise(text))
    assert expected_subset.issubset(tokens) or (expected_subset == set() and tokens == set())


def test_same_query_is_deterministic(tmp_path: Path) -> None:
    idx = tmp_path / "idx.json"
    _write_index(
        idx,
        [
            _chunk("c_a", "租約 固定 租期 兩年", 10),
            _chunk("c_b", "租客 押金 兩個月 加上 一期", 11),
        ],
    )
    service = TenancyRagService(index_path=idx)
    first = [h.id for h in service.retrieve("租約 租期", k=2)]
    second = [h.id for h in service.retrieve("租約 租期", k=2)]
    assert first == second
