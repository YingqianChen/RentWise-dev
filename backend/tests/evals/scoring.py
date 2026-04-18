"""Scoring helpers for the eval suite.

Field-level matching uses accept lists (``expected`` can be a string or a list
of acceptable synonyms). Numeric fields use range checks. No LLM-as-judge —
everything here is deterministic and cheap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Primitive matchers
# ---------------------------------------------------------------------------


_NORMALIZE_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _NORMALIZE_WS.sub(" ", text.strip().lower())


def fuzzy_field_match(expected: Any, actual: Any) -> bool:
    """True when *actual* matches any value in *expected* (normalised)."""
    if actual is None:
        return expected is None
    actual_s = _norm(str(actual))
    if not actual_s or actual_s in {"unknown", "none", "n/a"}:
        return expected is None
    accept = expected if isinstance(expected, (list, tuple)) else [expected]
    for candidate in accept:
        if candidate is None:
            continue
        if _norm(str(candidate)) in actual_s or actual_s in _norm(str(candidate)):
            return True
    return False


def numeric_in_range(actual: Any, bounds: Iterable[float]) -> bool:
    """True when *actual* parses to a number in the inclusive ``[low, high]`` range."""
    try:
        value = float(str(actual).replace(",", "").replace("$", "").replace("HKD", "").strip())
    except (TypeError, ValueError):
        return False
    low, high = list(bounds)
    return low <= value <= high


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class FieldResult:
    field: str
    passed: bool
    expected: Any
    actual: Any


@dataclass
class CaseResult:
    case_id: str
    fields: list[FieldResult] = field(default_factory=list)

    def field_passed(self, name: str) -> Optional[bool]:
        for fr in self.fields:
            if fr.field == name:
                return fr.passed
        return None


def aggregate_report(cases: list[CaseResult]) -> dict:
    """Roll up per-case field results into an overall + per-field pass-rate dict."""
    totals: dict[str, dict[str, int]] = {}
    total_checks = 0
    total_passes = 0
    failed_cases: list[dict] = []
    for case in cases:
        case_failures: list[dict] = []
        for fr in case.fields:
            bucket = totals.setdefault(fr.field, {"pass": 0, "fail": 0})
            bucket["pass" if fr.passed else "fail"] += 1
            total_checks += 1
            if fr.passed:
                total_passes += 1
            else:
                case_failures.append(
                    {"field": fr.field, "expected": fr.expected, "actual": fr.actual}
                )
        if case_failures:
            failed_cases.append({"case_id": case.case_id, "failures": case_failures})

    per_field = {
        name: {
            "pass_rate": round(b["pass"] / max(1, b["pass"] + b["fail"]), 3),
            "pass": b["pass"],
            "fail": b["fail"],
        }
        for name, b in totals.items()
    }
    return {
        "overall_pass_rate": round(total_passes / max(1, total_checks), 3),
        "total_cases": len(cases),
        "total_checks": total_checks,
        "per_field": per_field,
        "failed_cases": failed_cases,
    }
