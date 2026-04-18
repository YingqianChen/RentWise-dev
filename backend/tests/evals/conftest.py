"""Shared fixtures for the eval suite.

Evals are gated behind ``pytest.mark.eval`` and skipped by default. Run with::

    pytest -m eval -q

Every run writes a structured report to ``tests/evals/reports/last_run.json``
so regressions can be diffed commit-to-commit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPORTS_DIR = Path(__file__).parent / "reports"


def load_jsonl(name: str) -> list[dict]:
    """Load a ``.jsonl`` file from the fixtures directory."""
    path = FIXTURES_DIR / name
    if not path.exists():
        return []
    out: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name}:{line_no} — bad JSON: {exc}") from exc
    return out


@pytest.fixture(scope="session")
def golden_listings() -> list[dict]:
    return load_jsonl("golden_listings.jsonl")


@pytest.fixture(scope="session")
def golden_commutes() -> list[dict]:
    return load_jsonl("golden_commutes.jsonl")


@pytest.fixture(scope="session")
def eval_report_writer() -> Iterator:
    """Yield a callable that persists a JSON report under ``reports/``."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _write(name: str, payload: dict) -> Path:
        target = REPORTS_DIR / name
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    yield _write


_LLM_DEPENDENT_EVAL_MODULES = {
    "test_extraction_eval",
    "test_commute_agent_eval",
}


def pytest_collection_modifyitems(config, items):
    """Skip LLM-backed eval tests when creds aren't configured.

    Most evals call the real Groq LLM; without ``GROQ_API_KEY`` they
    deterministically fail. ``OLLAMA_HOST`` is *not* treated as evidence of
    working creds — the classroom Ollama endpoint is no longer reachable, and
    leaving it in the env from a prior shell session shouldn't trick the
    harness into running.

    Pure-BM25 evals (e.g. the tenancy RAG recall test) don't need an LLM, so
    they're exempt from the skip and always run when the user opts in with
    ``-m eval``.
    """
    if os.getenv("GROQ_API_KEY"):
        return
    skip_marker = pytest.mark.skip(reason="GROQ_API_KEY not set; LLM-backed evals skipped")
    for item in items:
        if "eval" not in item.keywords:
            continue
        module_name = item.module.__name__.rsplit(".", 1)[-1]
        if module_name in _LLM_DEPENDENT_EVAL_MODULES:
            item.add_marker(skip_marker)
