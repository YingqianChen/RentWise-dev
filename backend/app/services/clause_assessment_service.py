"""Clause assessment service for analyzing rental terms."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional
import re

from ..db.models import CandidateExtractedInfo, ClauseAssessment
from .tenancy_rag_service import TenancyChunk, TenancyRagService, get_tenancy_rag_service


logger = logging.getLogger(__name__)


# Topic → seed query for BM25. Keys align with the internal risk level names
# returned by ``_assess_*`` methods below. Values are whitespace-joined seed
# terms the tokeniser will split into jieba tokens that match the ordinance
# index.
_RAG_TOPIC_QUERIES: dict[str, str] = {
    "repair_tenant_heavy": "維修 責任 業主 租客 損壞 維護",
    "repair_unclear": "維修 責任 業主 租客 損壞 維護",
    "repair_supported_but_unconfirmed": "維修 責任 業主 租客 損壞 維護",
    "lease_unstable": "租約 租期 提前 終止 通知 退租",
    "lease_rigid": "租約 固定 租期 生約 死約 提前 終止",
    "move_in_mismatch": "交楼 入住 日期 租約 起租",
    "move_in_uncertain": "交楼 入住 日期 租約 起租",
}

_RAG_TOP_K = 5
_RAG_FINAL_REFS = 2
_RAG_QUOTE_MAX_CHARS = 180


class ClauseAssessmentService:
    """Assess key clause risk for a candidate."""

    def __init__(self, rag_service: Optional[TenancyRagService] = None) -> None:
        self._rag = rag_service


    @property
    def rag(self) -> TenancyRagService:
        if self._rag is None:
            self._rag = get_tenancy_rag_service()
        return self._rag

    _MONTH_NAMES = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }

    def assess(self, extracted_info: CandidateExtractedInfo, move_in_target: Optional[date] = None) -> ClauseAssessment:
        repair_level = self._assess_repair_responsibility(
            extracted_info.repair_responsibility,
            extracted_info.decision_signals,
        )
        lease_level = self._assess_lease_term(extracted_info.lease_term)
        move_in_level = self._assess_move_in_date(
            extracted_info.move_in_date,
            move_in_target,
            extracted_info.decision_signals,
        )
        clause_confidence = self._determine_confidence(repair_level, lease_level, move_in_level)
        clause_risk_flag = self._determine_risk_flag(repair_level, lease_level, move_in_level)
        summary = self._generate_summary(repair_level, lease_level, move_in_level, clause_risk_flag)
        return ClauseAssessment(
            candidate_id=extracted_info.candidate_id,
            repair_responsibility_level=repair_level,
            lease_term_level=lease_level,
            move_in_date_level=move_in_level,
            clause_confidence=clause_confidence,
            clause_risk_flag=clause_risk_flag,
            summary=summary,
        )

    def _assess_repair_responsibility(
        self,
        value: Optional[str],
        signals: list[dict[str, str]] | None = None,
    ) -> str:
        signal_text = self._signal_text(signals, {"repair_support_signal"})
        if self._is_unknown(value) and not signal_text:
            return "unknown"

        lower = f"{value or ''} {signal_text}".lower()
        repair_topic = any(
            keyword in lower
            for keyword in [
                "repair",
                "repairs",
                "appliance",
                "appliances",
                "maintenance",
                "fix",
                "broken",
                "包维修",
                "维修",
                "宿舍",
            ]
        )
        if any(
            keyword in lower
            for keyword in [
                "tenant responsible",
                "tenant liable",
                "all repairs by tenant",
                "tenant pays for repairs",
                "tenant handles repairs",
                "at tenant expense",
            ]
        ):
            return "tenant_heavy"

        owner_terms = ["landlord", "owner", "landlady", "lessor"]
        owner_verbs = [
            "responsible",
            "handle",
            "handles",
            "handled",
            "cover",
            "covers",
            "covered",
            "pay",
            "pays",
            "paid",
            "will pay",
            "included",
            "include",
        ]
        explicit_owner_signal = repair_topic and any(term in lower for term in owner_terms) and any(
            verb in lower for verb in owner_verbs
        )
        if "school dorm" in lower or "dorm" in lower or "宿舍" in lower:
            explicit_owner_signal = explicit_owner_signal or any(
                token in lower
                for token in ["maintenance included", "包维修", "repairs included", "school covers repairs"]
            )
        if explicit_owner_signal:
            return "clear"

        intermediary_terms = ["agency", "agent", "management office", "management", "property manager"]
        support_verbs = ["pay", "pays", "paid", "will pay", "cover", "covers", "covered", "handle", "handles", "handled"]
        supportive_intermediary_signal = repair_topic and any(term in lower for term in intermediary_terms) and any(
            verb in lower for verb in support_verbs
        )
        if supportive_intermediary_signal or ("they will pay" in lower and repair_topic):
            return "supported_but_unconfirmed"

        if "mutual" in lower:
            return "unclear"
        return "unclear"

    def _assess_lease_term(self, value: Optional[str]) -> str:
        if self._is_unknown(value):
            return "unknown"
        lower = str(value).lower()
        if self._contains_any(
            lower,
            [
                "month-to-month",
                "monthly rolling",
                "rolling monthly",
                "short term",
                "short-term",
                "temporary stay",
                "weekly stay",
                "daily rental",
                "can leave anytime",
                "license agreement",
            ],
        ):
            return "unstable"

        rigid_signal = self._contains_any(
            lower,
            ["fixed", "non-break", "no early termination", "must complete the lease", "strict lease"],
        )
        flexibility_signal = self._contains_any(
            lower,
            [
                "optional",
                "break clause",
                "renewable",
                "negotiable",
                "flexible",
                "1 year fixed 1 year optional",
                "two-year lease with break clause",
            ],
        )
        if rigid_signal and not flexibility_signal:
            return "rigid"

        has_standard_duration = bool(re.search(r"\b(6|12|18|24)\s*(month|months)\b", lower)) or self._contains_any(
            lower,
            [
                "1 year",
                "2 years",
                "one year",
                "two years",
                "1+1",
                "1 year fixed 1 year optional",
                "two-year lease",
                "standard lease",
                "renewable",
                "optional",
                "break clause",
            ],
        )
        if has_standard_duration:
            return "standard"

        return "standard"

    def _assess_move_in_date(
        self,
        value: Optional[str],
        target_date: Optional[date],
        signals: list[dict[str, str]] | None = None,
    ) -> str:
        signal_text = self._signal_text(signals, {"move_in_timing_signal"})
        if self._is_unknown(value) and not signal_text:
            return "unknown"
        lower = f"{value or ''} {signal_text}".lower()
        if self._contains_any(lower, ["immediate", "anytime", "available now", "ready now", "move in now", "vacant now"]):
            return "fit"
        if self._contains_any(
            lower,
            [
                "semester start",
                "start of semester",
                "start of school",
                "school starts",
                "start of term",
                "term starts",
                "开学",
                "开学时",
                "开学入住",
            ],
        ):
            if target_date is None:
                return "fit"
            if target_date.month in {8, 9, 1, 2}:
                return "fit"
            return "uncertain"
        if self._contains_any(lower, ["negotiable", "flexible", "to be discussed", "can discuss"]):
            return "uncertain" if target_date else "fit"
        if target_date is None:
            return "uncertain"

        available_year, available_month = self._extract_year_month(lower)
        if available_month is None:
            return "uncertain"

        target_year = target_date.year
        target_month = target_date.month

        if available_year is not None:
            if available_year > target_year:
                return "mismatch"
            if available_year < target_year:
                return "fit"

        if available_month > target_month:
            return "mismatch"
        if available_month <= target_month:
            return "fit"
        return "uncertain"

    def _determine_confidence(self, repair_level: str, lease_level: str, move_in_level: str) -> str:
        unknown_count = sum(level == "unknown" for level in [repair_level, lease_level, move_in_level])
        if unknown_count == 0 and repair_level != "supported_but_unconfirmed":
            return "high"
        if unknown_count == 1 or repair_level == "supported_but_unconfirmed":
            return "medium"
        return "low"

    def _determine_risk_flag(self, repair_level: str, lease_level: str, move_in_level: str) -> str:
        if repair_level == "tenant_heavy" or lease_level == "unstable":
            return "high_risk"
        if (
            "unknown" in {repair_level, lease_level, move_in_level}
            or repair_level in {"unclear", "supported_but_unconfirmed"}
            or move_in_level in {"uncertain", "mismatch"}
        ):
            return "needs_confirmation"
        return "none"

    def _generate_summary(self, repair_level: str, lease_level: str, move_in_level: str, clause_risk_flag: str) -> str:
        parts = []
        if repair_level == "tenant_heavy":
            parts.append("Repair responsibility appears heavily shifted to the tenant.")
        elif repair_level == "supported_but_unconfirmed":
            parts.append(
                "There is a positive signal that repair support exists, but the final contractual responsibility is still not explicit."
            )
        elif repair_level in {"unclear", "unknown"}:
            parts.append("Repair responsibility still needs confirmation.")
        else:
            parts.append("Repair responsibility appears relatively clear.")

        if lease_level == "rigid":
            parts.append("The lease terms may be less flexible than ideal.")
        elif lease_level == "unstable":
            parts.append("The lease arrangement looks unstable or short term.")

        if move_in_level in {"unknown", "uncertain", "mismatch"}:
            parts.append("Move-in timing still needs confirmation.")

        if clause_risk_flag == "high_risk":
            parts.append("This candidate currently carries elevated clause risk.")
        elif clause_risk_flag == "needs_confirmation":
            parts.append("Key terms are still incomplete.")

        return " ".join(parts) if parts else "The clause picture is reasonably clear."

    def _is_unknown(self, value: Optional[str]) -> bool:
        if value is None:
            return True
        return str(value).strip().lower() in {"", "unknown", "n/a", "none"}

    def _contains_any(self, value: str, keywords: list[str]) -> bool:
        return any(keyword in value for keyword in keywords)

    def _extract_year_month(self, value: str) -> tuple[Optional[int], Optional[int]]:
        iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})(?:[-/]\d{1,2})?\b", value)
        if iso_match:
            return int(iso_match.group(1)), int(iso_match.group(2))

        slash_month_match = re.search(r"\b(\d{1,2})[-/](20\d{2})\b", value)
        if slash_month_match:
            return int(slash_month_match.group(2)), int(slash_month_match.group(1))

        for month_name, month_number in self._MONTH_NAMES.items():
            if month_name in value:
                year_match = re.search(r"\b(20\d{2})\b", value)
                return (int(year_match.group(1)) if year_match else None, month_number)

        month_number_match = re.search(r"\b(?:from|available|ready|move in)\s+(\d{1,2})\b", value)
        if month_number_match:
            return None, int(month_number_match.group(1))

        return None, None

    def _signal_text(self, signals: list[dict[str, str]] | None, keys: set[str]) -> str:
        if not signals:
            return ""

        fragments: list[str] = []
        for signal in signals:
            if signal.get("key") in keys:
                fragments.extend(
                    part
                    for part in [signal.get("label", ""), signal.get("evidence", ""), signal.get("note", "")]
                    if part
                )
        return " ".join(fragments)

    # ------------------------------------------------------------------
    # RAG enrichment

    async def attach_legal_references(self, assessment: ClauseAssessment) -> ClauseAssessment:
        """Populate ``assessment.legal_references`` from the tenancy ordinance.

        No-op when ``clause_risk_flag == "none"`` — clean clauses don't warrant
        surfacing "here is the law that governs this" noise. Otherwise:

            1. Build a seed query by concatenating ordinance-topic queries for
               each risk level that tripped.
            2. BM25 top-5 over the guide.
            3. LLM rerank down to up to 2 refs; on any LLM failure fall back to
               raw BM25 top-2 so the UI still has something to show.
        """
        if assessment.clause_risk_flag == "none":
            assessment.legal_references = None
            return assessment

        topics = _collect_topics(assessment)
        if not topics:
            assessment.legal_references = None
            return assessment

        query = " ".join(_RAG_TOPIC_QUERIES[t] for t in topics)
        candidates = self.rag.retrieve(query, k=_RAG_TOP_K)
        if not candidates:
            assessment.legal_references = None
            return assessment

        refs = await _llm_rerank(candidates, topics) or _fallback_refs(candidates)
        assessment.legal_references = refs or None
        return assessment


def _collect_topics(assessment: ClauseAssessment) -> list[str]:
    """Map assessment levels to topic keys. Preserves ordering for determinism."""
    topics: list[str] = []
    if assessment.repair_responsibility_level == "tenant_heavy":
        topics.append("repair_tenant_heavy")
    elif assessment.repair_responsibility_level == "unclear":
        topics.append("repair_unclear")
    elif assessment.repair_responsibility_level == "supported_but_unconfirmed":
        topics.append("repair_supported_but_unconfirmed")

    if assessment.lease_term_level == "unstable":
        topics.append("lease_unstable")
    elif assessment.lease_term_level == "rigid":
        topics.append("lease_rigid")

    if assessment.move_in_date_level == "mismatch":
        topics.append("move_in_mismatch")
    elif assessment.move_in_date_level == "uncertain":
        topics.append("move_in_uncertain")
    return topics


def _fallback_refs(candidates: list[TenancyChunk]) -> list[dict[str, Any]]:
    return [
        {
            "quote": _truncate_quote(chunk.text),
            "source_page": chunk.source_page,
            "chunk_id": chunk.id,
        }
        for chunk in candidates[:_RAG_FINAL_REFS]
    ]


def _truncate_quote(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= _RAG_QUOTE_MAX_CHARS:
        return text
    return text[: _RAG_QUOTE_MAX_CHARS - 1].rstrip() + "…"


async def _llm_rerank(
    candidates: list[TenancyChunk],
    topics: list[str],
) -> Optional[list[dict[str, Any]]]:
    """Ask the LLM to pick the most relevant ids; None on any failure."""
    catalogue_lines: list[str] = []
    for chunk in candidates:
        catalogue_lines.append(f"[{chunk.id}] (p{chunk.source_page}) {chunk.text[:240]}")
    catalogue = "\n".join(catalogue_lines)

    topic_label = ", ".join(topics)
    prompt = (
        "You are reranking legal excerpts for a Hong Kong tenancy clause review.\n"
        f"The flagged assessment topics are: {topic_label}.\n"
        "Below are BM25 candidates from 《業主與租客（綜合）條例》. Pick up to "
        f"{_RAG_FINAL_REFS} excerpts that most directly inform the flagged topics. "
        "Prefer excerpts that state obligations, rights, or timelines over generic "
        "introductory text. If none are relevant, return an empty list.\n\n"
        "Candidates:\n"
        f"{catalogue}\n\n"
        "Respond with strict JSON of the form:\n"
        '{"selected_ids": ["chunk_id_1", "chunk_id_2"]}'
    )

    try:
        from ..integrations.llm.utils import chat_completion_json  # local — avoids
        # forcing config load (which requires SECRET_KEY / DATABASE_URL) on modules
        # that merely import ClauseAssessmentService for type use in tests.

        response = await chat_completion_json(prompt, temperature=0.0, max_tokens=200)
    except Exception as exc:  # noqa: BLE001 — any LLM failure falls back to BM25
        logger.warning("tenancy RAG rerank failed (%s); falling back to BM25 top-k", exc)
        return None

    if not isinstance(response, dict):
        return None
    raw_ids = response.get("selected_ids") or []
    if not isinstance(raw_ids, list):
        return None

    by_id = {chunk.id: chunk for chunk in candidates}
    picked: list[dict[str, Any]] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        chunk = by_id.get(raw_id)
        if chunk is None:
            continue
        picked.append(
            {
                "quote": _truncate_quote(chunk.text),
                "source_page": chunk.source_page,
                "chunk_id": chunk.id,
            }
        )
        if len(picked) >= _RAG_FINAL_REFS:
            break
    return picked or None
