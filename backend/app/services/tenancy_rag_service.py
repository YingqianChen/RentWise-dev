"""BM25 retrieval over the HK tenancy ordinance guide.

The guide is OCR'd into chunks offline by
``backend/scripts/build_tenancy_index.py`` and the result is committed to
``backend/app/data/tenancy_index.json``. At runtime we lazily load that JSON
once per process, build an in-memory ``BM25Okapi`` over the pre-tokenised
chunks, and serve ``retrieve(query, k)`` hits — no dense embeddings, no
third-party APIs, all on-box.

Call sites: ``clause_assessment_service`` enriches each non-``none`` risk flag
with up to a few paragraphs of officialdom-sourced context so the UI can show
"why does this clause look suspicious?" links back to the ordinance itself.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import jieba
from rank_bm25 import BM25Okapi


logger = logging.getLogger(__name__)

_INDEX_PATH_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "tenancy_index.json"


@dataclass(frozen=True)
class TenancyChunk:
    """A single retrievable paragraph with its source page."""

    id: str
    text: str
    source_page: int
    score: float = 0.0


class TenancyRagService:
    """Lazy-loaded BM25 retriever over the tenancy guide."""

    def __init__(self, index_path: Path = _INDEX_PATH_DEFAULT) -> None:
        self._index_path = index_path
        self._chunks: list[dict] = []
        self._bm25: Optional[BM25Okapi] = None
        self._loaded = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Loading

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()

    def _load(self) -> None:
        if not self._index_path.exists():
            logger.warning(
                "tenancy rag index missing at %s — retrieval will return empty results. "
                "Run `python -m scripts.build_tenancy_index` to build it.",
                self._index_path,
            )
            self._loaded = True
            return
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("failed to load tenancy index: %s", exc)
            self._loaded = True
            return

        self._chunks = payload.get("chunks", []) or []
        tokenised = [chunk.get("tokens") or [] for chunk in self._chunks]
        if tokenised:
            self._bm25 = BM25Okapi(tokenised)
        self._loaded = True
        logger.info("loaded tenancy index with %d chunks", len(self._chunks))

    # ------------------------------------------------------------------
    # Public API

    def retrieve(self, query: str, k: int = 5) -> list[TenancyChunk]:
        """Return BM25-ranked chunks for ``query``.

        Empty / whitespace queries return ``[]``. If ``k`` exceeds the index
        size, the full index is returned. Scores below zero (negative IDF
        because of shared vocabulary with short queries) are still returned so
        the caller can decide how to threshold.
        """
        self._ensure_loaded()
        if self._bm25 is None or not self._chunks:
            return []
        if not query or not query.strip():
            return []

        tokens = _tokenise(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        k = max(1, min(int(k), len(self._chunks)))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        hits: list[TenancyChunk] = []
        for idx in top_indices:
            chunk = self._chunks[idx]
            hits.append(
                TenancyChunk(
                    id=chunk.get("id") or f"chunk_{idx}",
                    text=chunk.get("text", ""),
                    source_page=int(chunk.get("source_page", 0)),
                    score=float(scores[idx]),
                )
            )
        return hits

    @property
    def chunk_count(self) -> int:
        self._ensure_loaded()
        return len(self._chunks)


# ----------------------------------------------------------------------
# Tokenisation — must match ``build_tenancy_index._tokenise`` in spirit so
# query tokens line up with index tokens. Kept in sync by hand; any change
# here should be mirrored in the build script and the index rebuilt.


def _tokenise(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in jieba.cut_for_search(text):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"[\W_]+", tok):
            continue
        tokens.append(tok.lower())
    return tokens


# ----------------------------------------------------------------------
# Singleton — service is stateless from the caller's POV; one in-memory
# BM25 matrix per process is plenty.

_default_service: Optional[TenancyRagService] = None


def get_tenancy_rag_service() -> TenancyRagService:
    global _default_service
    if _default_service is None:
        _default_service = TenancyRagService()
    return _default_service
