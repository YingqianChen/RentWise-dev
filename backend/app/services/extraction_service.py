"""Extraction service for parsing rental listing text."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from ..db.models import CandidateExtractedInfo, CandidateListing
from ..integrations.llm.prompts import EXTRACTION_PROMPT, LISTING_NAME_PROMPT
from ..integrations.llm.utils import chat_completion_json

logger = logging.getLogger(__name__)


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


class ExtractionService:
    """Service for extracting structured information from listing text."""

    @staticmethod
    def _collect_ocr_texts(candidate: CandidateListing) -> list[str]:
        """Collect OCR texts from uploaded source assets."""
        if not getattr(candidate, "source_assets", None):
            return []
        return [
            asset.ocr_text.strip()
            for asset in candidate.source_assets
            if asset.ocr_text and asset.ocr_text.strip()
        ]

    @staticmethod
    def _build_extraction_context(candidate: CandidateListing, ocr_texts: list[str]) -> str:
        """Build a source-aware evidence bundle for extraction."""
        sections: list[str] = []

        def add_section(title: str, value: Optional[str]) -> None:
            if value and value.strip():
                sections.append(f"[{title}]\n{value.strip()}")

        add_section("Listing", candidate.raw_listing_text)
        add_section("Chat", candidate.raw_chat_text)
        add_section("Notes", candidate.raw_note_text)
        if ocr_texts:
            sections.append("[OCR]\n" + "\n\n".join(ocr_texts))

        if sections:
            return "\n\n".join(sections)

        return (candidate.combined_text or "").strip()

    async def extract(self, candidate: CandidateListing) -> CandidateExtractedInfo:
        """Extract structured information from a candidate's combined text."""
        ocr_texts = self._collect_ocr_texts(candidate)
        if not candidate.combined_text:
            return CandidateExtractedInfo(
                candidate_id=candidate.id,
                decision_signals=[],
                raw_facts=[],
                ocr_texts=ocr_texts,
            )

        prompt = EXTRACTION_PROMPT.format(
            text=self._build_extraction_context(candidate, ocr_texts)
        )
        try:
            data = await chat_completion_json(prompt=prompt, temperature=0.0)
        except Exception as exc:
            logger.error("Extraction failed: %s", exc)
            return CandidateExtractedInfo(
                candidate_id=candidate.id,
                decision_signals=[],
                raw_facts=[],
                ocr_texts=ocr_texts,
            )

        return CandidateExtractedInfo(
            candidate_id=candidate.id,
            monthly_rent=normalize_value(data.get("monthly_rent", "")),
            management_fee_amount=normalize_value(data.get("management_fee_amount", "")),
            management_fee_included=parse_bool_value(str(data.get("management_fee_included", ""))),
            rates_amount=normalize_value(data.get("rates_amount", "")),
            rates_included=parse_bool_value(str(data.get("rates_included", ""))),
            deposit=normalize_value(data.get("deposit", "")),
            agent_fee=normalize_value(data.get("agent_fee", "")),
            lease_term=normalize_value(data.get("lease_term", "")),
            move_in_date=normalize_value(data.get("move_in_date", "")),
            repair_responsibility=normalize_value(data.get("repair_responsibility", "")),
            district=normalize_value(data.get("district", "")),
            furnished=normalize_value(data.get("furnished", "")),
            size_sqft=normalize_value(data.get("size_sqft", "")),
            bedrooms=normalize_value(data.get("bedrooms", "")),
            suspected_sdu=parse_bool_value(str(data.get("suspected_sdu", ""))),
            sdu_detection_reason=normalize_optional_value(str(data.get("sdu_detection_reason", ""))),
            address_text=normalize_optional_value(str(data.get("address_text", ""))),
            building_name=normalize_optional_value(str(data.get("building_name", ""))),
            nearest_station=normalize_optional_value(str(data.get("nearest_station", ""))),
            location_confidence=normalize_value(data.get("location_confidence", "unknown")),
            location_source="extracted",
            decision_signals=normalize_decision_signals(data.get("decision_signals", [])),
            raw_facts=normalize_raw_facts(data.get("raw_facts", [])),
            ocr_texts=ocr_texts,
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
