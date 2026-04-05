"""Extraction service for parsing rental listing text."""

from __future__ import annotations

from typing import Optional

from ..db.models import CandidateExtractedInfo, CandidateListing
from ..integrations.llm.prompts import EXTRACTION_PROMPT, LISTING_NAME_PROMPT
from ..integrations.llm.utils import chat_completion_json


def normalize_value(value: str) -> str:
    """Normalize extracted values to a stable string representation."""
    if not value or value.lower() in {"unknown", "n/a", "none", ""}:
        return "unknown"
    return value.strip()


def normalize_optional_value(value: str) -> Optional[str]:
    """Normalize extracted values while preserving null for missing hints."""
    if not value or value.lower() in {"unknown", "n/a", "none", ""}:
        return None
    return value.strip()


def parse_bool_value(value: str) -> Optional[bool]:
    """Parse boolean-like strings returned by the extractor."""
    if not value or value.lower() in {"unknown", "n/a", "none", ""}:
        return None

    lower = value.lower().strip()
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

    async def extract(self, candidate: CandidateListing) -> CandidateExtractedInfo:
        """Extract structured information from a candidate's combined text."""
        ocr_texts = self._collect_ocr_texts(candidate)
        if not candidate.combined_text:
            return CandidateExtractedInfo(candidate_id=candidate.id, ocr_texts=ocr_texts)

        prompt = EXTRACTION_PROMPT.format(text=candidate.combined_text)
        try:
            data = await chat_completion_json(prompt=prompt, temperature=0.0)
        except Exception as exc:
            print(f"Extraction failed: {exc}")
            return CandidateExtractedInfo(candidate_id=candidate.id)

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
            print(f"Name generation failed: {exc}")

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

        from datetime import datetime

        return f"Listing {datetime.now().strftime('%m%d%H%M')}"[:20]
