"""Extraction service for parsing rental listing text."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..db.models import CandidateExtractedInfo, CandidateListing
from ..integrations.llm.prompts import EXTRACTION_PROMPT, LISTING_NAME_PROMPT
from ..integrations.llm.utils import chat_completion_json
from .analysis_errors import AnalysisError, analysis_error, classify_extraction_exception
from .candidate_field_evidence_service import (
    CandidateEvidenceSource,
    MergedFieldFact,
    merge_field_claims,
    verify_field_claims,
)

logger = logging.getLogger(__name__)

REQUIRED_SUPPLEMENTAL_KEYS = {
    "furnished",
    "size_sqft",
    "bedrooms",
    "suspected_sdu",
    "sdu_detection_reason",
    "decision_signals",
    "raw_facts",
}


@dataclass(frozen=True, slots=True)
class CandidateExtractionResult:
    """Compatibility snapshot plus the new source-backed field results."""

    extracted_info: CandidateExtractedInfo
    field_facts: tuple[MergedFieldFact, ...]


def _coerce_to_str(value: object) -> str:
    """Coerce arbitrary LLM-return values into a safe string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)


def normalize_value(value: object) -> str:
    """Normalize extracted values to a stable string representation."""
    text = _coerce_to_str(value)
    if not text or text.lower().strip() in {"unknown", "n/a", "none", ""}:
        return "unknown"
    return text.strip()


def normalize_optional_value(value: object) -> Optional[str]:
    """Normalize extracted values while preserving null for missing hints."""
    text = _coerce_to_str(value)
    if not text or text.lower().strip() in {"unknown", "n/a", "none", ""}:
        return None
    return text.strip()


def parse_bool_value(value: object) -> Optional[bool]:
    """Parse boolean-like values returned by the extractor."""
    if isinstance(value, bool):
        return value
    text = _coerce_to_str(value)
    if not text or text.lower().strip() in {"unknown", "n/a", "none", ""}:
        return None

    lower = text.lower().strip()
    if lower in {
        "true",
        "yes",
        "included",
        "include",
        "including",
        "covered",
        "cover",
    }:
        return True
    if lower in {
        "false",
        "no",
        "excluded",
        "exclude",
        "excluding",
        "separate",
        "charged separately",
    }:
        return False
    return None


def normalize_signal_value(value: object) -> str:
    """Normalize signal values into compact strings."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_raw_facts(value: object) -> list[str]:
    """Normalize the free-form raw_facts list returned by the extractor."""
    if not isinstance(value, list):
        return []
    facts: list[str] = []
    for item in value:
        text = _coerce_to_str(item).strip()
        if not text or text.lower() in {"unknown", "n/a", "none"}:
            continue
        facts.append(text[:200])
    return facts


def normalize_decision_signals(value: object) -> list[dict[str, str]]:
    """Normalize flexible decision signals from the extractor."""
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    allowed_sources = {"listing", "chat", "note", "ocr", "mixed"}

    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue

        key = normalize_signal_value(raw_item.get("key")).lower().replace(" ", "_")
        category = normalize_signal_value(raw_item.get("category")).lower().replace(" ", "_")
        label = normalize_signal_value(raw_item.get("label"))
        source = normalize_signal_value(raw_item.get("source")).lower()
        evidence = normalize_signal_value(raw_item.get("evidence"))
        note = normalize_signal_value(raw_item.get("note"))

        if not key or not category or not label or not evidence:
            continue

        normalized.append(
            {
                "key": key,
                "category": category,
                "label": label,
                "source": source if source in allowed_sources else "mixed",
                "evidence": evidence,
                "note": note,
            }
        )

    return normalized


def validate_extraction_payload(value: object) -> dict[str, object]:
    """Reject incomplete or structurally invalid model output."""
    if not isinstance(value, dict):
        raise analysis_error("invalid_model_output", retryable=True)

    if set(value) != {"field_claims", "supplemental"}:
        raise analysis_error("invalid_model_output", retryable=True)

    field_claims = value["field_claims"]
    supplemental = value["supplemental"]
    if not isinstance(field_claims, list) or not isinstance(supplemental, dict):
        raise analysis_error("invalid_model_output", retryable=True)

    if set(supplemental) != REQUIRED_SUPPLEMENTAL_KEYS:
        raise analysis_error("invalid_model_output", retryable=True)

    if not isinstance(supplemental["decision_signals"], list) or not isinstance(
        supplemental["raw_facts"], list
    ):
        raise analysis_error("invalid_model_output", retryable=True)

    for key in REQUIRED_SUPPLEMENTAL_KEYS.difference({"decision_signals", "raw_facts"}):
        if isinstance(supplemental[key], (dict, list)):
            raise analysis_error("invalid_model_output", retryable=True)

    return value


class ExtractionService:
    """Service for extracting structured information from listing text."""

    @staticmethod
    def _collect_sources(candidate: CandidateListing) -> tuple[CandidateEvidenceSource, ...]:
        """Keep each user-supplied source independently addressable."""
        sources: list[CandidateEvidenceSource] = []

        def add_text_source(source_type: str, value: Optional[str]) -> None:
            if value and value.strip():
                sources.append(CandidateEvidenceSource(source_type=source_type, text=value.strip()))

        add_text_source("listing", candidate.raw_listing_text)
        add_text_source("chat", candidate.raw_chat_text)
        add_text_source("note", candidate.raw_note_text)

        for asset in getattr(candidate, "source_assets", None) or []:
            if asset.ocr_text and asset.ocr_text.strip():
                sources.append(
                    CandidateEvidenceSource(
                        source_type="image_ocr",
                        source_asset_id=asset.id,
                        filename=asset.original_filename,
                        text=asset.ocr_text.strip(),
                    )
                )

        return tuple(sources)

    @staticmethod
    def _build_extraction_context(sources: tuple[CandidateEvidenceSource, ...]) -> str:
        """Build a source-aware evidence bundle for extraction."""
        sections: list[str] = []

        for source in sources:
            source_label = f"SOURCE {source.source_type}"
            if source.source_asset_id is not None:
                safe_filename = (source.filename or "image").replace("\n", " ").replace("]", "")
                source_label += f" asset_id={source.source_asset_id} filename={safe_filename}"
            sections.append(f"[{source_label}]\n{source.text}")
        return "\n\n".join(sections)

    @staticmethod
    def _legacy_value(facts_by_key: dict[str, MergedFieldFact], field_key: str) -> object | None:
        """Only project explicit facts into the pre-Sprint-2 assessment tables."""
        fact = facts_by_key[field_key]
        return fact.system_value if fact.system_state == "explicit" else None

    @staticmethod
    def _location_metadata(facts_by_key: dict[str, MergedFieldFact]) -> tuple[str, str]:
        location_keys = ("address_text", "building_name", "nearest_station", "district")
        explicit_keys = [
            field_key
            for field_key in location_keys
            if facts_by_key[field_key].system_state == "explicit"
        ]
        if "address_text" in explicit_keys:
            confidence = "high"
        elif "building_name" in explicit_keys or "nearest_station" in explicit_keys:
            confidence = "medium"
        elif "district" in explicit_keys:
            confidence = "low"
        else:
            return "unknown", "unknown"

        source_types = {
            claim.source_type
            for field_key in explicit_keys
            for claim in facts_by_key[field_key].evidence
            if claim.claim_kind == "explicit"
        }
        source = next(iter(source_types)) if len(source_types) == 1 else "mixed"
        return confidence, source

    async def extract(self, candidate: CandidateListing) -> CandidateExtractedInfo:
        """Return the compatibility snapshot used by existing callers."""
        result = await self.extract_with_evidence(candidate)
        return result.extracted_info

    async def extract_with_evidence(self, candidate: CandidateListing) -> CandidateExtractionResult:
        """Extract, verify, and merge source-backed field claims."""
        sources = self._collect_sources(candidate)
        context = self._build_extraction_context(sources)
        if not context:
            raise analysis_error("no_usable_text", retryable=True)

        prompt = EXTRACTION_PROMPT.format(text=context)
        try:
            data = await chat_completion_json(prompt=prompt, temperature=0.0)
        except AnalysisError:
            raise
        except Exception as exc:
            failure = classify_extraction_exception(exc)
            logger.exception("Extraction failed with code %s", failure.code)
            raise failure from exc

        data = validate_extraction_payload(data)
        verified_claims = verify_field_claims(data["field_claims"], sources)
        field_facts = merge_field_claims(verified_claims)
        facts_by_key = {fact.field_key: fact for fact in field_facts}
        supplemental = data["supplemental"]
        location_confidence, location_source = self._location_metadata(facts_by_key)
        ocr_texts = [source.text for source in sources if source.source_type == "image_ocr"]

        extracted_info = CandidateExtractedInfo(
            candidate_id=candidate.id,
            monthly_rent=normalize_value(self._legacy_value(facts_by_key, "monthly_rent")),
            management_fee_amount=normalize_value(
                self._legacy_value(facts_by_key, "management_fee_amount")
            ),
            management_fee_included=self._legacy_value(
                facts_by_key, "management_fee_included"
            ),
            rates_amount=normalize_value(self._legacy_value(facts_by_key, "rates_amount")),
            rates_included=self._legacy_value(facts_by_key, "rates_included"),
            deposit=normalize_value(self._legacy_value(facts_by_key, "deposit")),
            agent_fee=normalize_value(self._legacy_value(facts_by_key, "agent_fee")),
            lease_term=normalize_value(self._legacy_value(facts_by_key, "lease_term")),
            move_in_date=normalize_value(self._legacy_value(facts_by_key, "move_in_date")),
            repair_responsibility=normalize_value(
                self._legacy_value(facts_by_key, "repair_responsibility")
            ),
            district=normalize_value(self._legacy_value(facts_by_key, "district")),
            furnished=normalize_value(supplemental.get("furnished", "")),
            size_sqft=normalize_value(supplemental.get("size_sqft", "")),
            bedrooms=normalize_value(supplemental.get("bedrooms", "")),
            suspected_sdu=parse_bool_value(str(supplemental.get("suspected_sdu", ""))),
            sdu_detection_reason=normalize_optional_value(
                str(supplemental.get("sdu_detection_reason", ""))
            ),
            address_text=normalize_optional_value(
                self._legacy_value(facts_by_key, "address_text")
            ),
            building_name=normalize_optional_value(
                self._legacy_value(facts_by_key, "building_name")
            ),
            nearest_station=normalize_optional_value(
                self._legacy_value(facts_by_key, "nearest_station")
            ),
            location_confidence=location_confidence,
            location_source=location_source,
            decision_signals=normalize_decision_signals(
                supplemental.get("decision_signals", [])
            ),
            raw_facts=normalize_raw_facts(supplemental.get("raw_facts", [])),
            ocr_texts=ocr_texts,
        )
        return CandidateExtractionResult(
            extracted_info=extracted_info,
            field_facts=field_facts,
        )

    async def generate_listing_name(
        self,
        extracted_info: CandidateExtractedInfo,
        combined_text: str,
    ) -> str:
        """Generate a short user-facing listing name."""
        text_preview = combined_text[:500] if combined_text else "No listing text provided."

        prompt = LISTING_NAME_PROMPT.format(
            combined_text=text_preview,
            monthly_rent=extracted_info.monthly_rent or "unknown",
            lease_term=extracted_info.lease_term or "unknown",
            furnished=extracted_info.furnished or "unknown",
        )

        try:
            result = await chat_completion_json(prompt=prompt, temperature=0.3)
            name = result.get("name", "")
            if name and len(name) <= 20:
                return name.strip()
        except Exception as exc:
            logger.error("Name generation failed: %s", exc)

        return self._generate_fallback_name(extracted_info, combined_text)

    def _generate_fallback_name(
        self,
        extracted_info: CandidateExtractedInfo,
        combined_text: str,
    ) -> str:
        """Generate a deterministic fallback name when LLM naming fails."""
        parts: list[str] = []

        district = (extracted_info.district or "").strip()
        if district and district.lower() != "unknown":
            parts.append(district)
        else:
            area_keywords = [
                ("Mong Kok", ["mong kok", "mongkok"]),
                ("Causeway Bay", ["causeway bay"]),
                ("Central", ["central"]),
                ("Wan Chai", ["wan chai", "wanchai"]),
                ("Tsim Sha Tsui", ["tsim sha tsui", "tst"]),
                ("Sham Shui Po", ["sham shui po"]),
                ("Kwun Tong", ["kwun tong"]),
                ("Sha Tin", ["sha tin"]),
                ("Tsuen Wan", ["tsuen wan"]),
                ("Tuen Mun", ["tuen mun"]),
                ("Yuen Long", ["yuen long"]),
            ]

            text_lower = combined_text.lower() if combined_text else ""
            for area_name, keywords in area_keywords:
                if any(keyword in text_lower for keyword in keywords):
                    parts.append(area_name)
                    break

        if extracted_info.monthly_rent and extracted_info.monthly_rent != "unknown":
            rent = (
                extracted_info.monthly_rent.replace("$", "")
                .replace("HKD", "")
                .replace("hkd", "")
                .replace(",", "")
                .strip()
            )
            if rent:
                parts.append(f"${rent}")

        if parts:
            return " ".join(parts)[:20]

        return f"Listing {datetime.now().strftime('%m%d%H%M')}"[:20]
