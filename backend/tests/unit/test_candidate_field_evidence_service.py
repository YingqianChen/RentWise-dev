from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_field_evidence_service import (
    CandidateEvidenceSource,
    merge_field_claims,
    verify_field_claims,
)


def raw_claim(
    field_key: str,
    value: object,
    quote: str,
    *,
    source_type: str = "listing",
    source_asset_id: object = None,
    claim_kind: str = "explicit",
    confidence: str = "high",
) -> dict[str, object]:
    return {
        "field_key": field_key,
        "value": value,
        "source_type": source_type,
        "source_asset_id": source_asset_id,
        "quote": quote,
        "claim_kind": claim_kind,
        "confidence": confidence,
    }


class CandidateFieldEvidenceServiceTests(TestCase):
    def test_quote_verification_allows_only_safe_format_normalization(self):
        sources = (CandidateEvidenceSource("listing", "Rent — ‘all in’：HKD 18,000"),)
        verified = verify_field_claims(
            [raw_claim("monthly_rent", 18000, "rent - 'all in':hkd 18,000")],
            sources,
        )
        self.assertEqual(len(verified), 1)

    def test_verification_rejects_wrong_types_sources_and_quotes(self):
        sources = (CandidateEvidenceSource("listing", "Rent $18,000. Management included."),)
        claims = verify_field_claims(
            [
                raw_claim("monthly_rent", "18000", "Rent $18,000"),
                raw_claim("monthly_rent", 18000, "Rent $19,000"),
                raw_claim("management_fee_included", "yes", "Management included"),
                raw_claim("monthly_rent", 18000, "Rent $18,000", source_type="chat"),
                raw_claim("not_a_field", "value", "Rent $18,000"),
            ],
            sources,
        )
        self.assertEqual(claims, ())

    def test_explicit_claim_outweighs_different_inference(self):
        sources = (
            CandidateEvidenceSource("listing", "Rent $18,000"),
            CandidateEvidenceSource("note", "Budget estimate suggests $20,000"),
        )
        verified = verify_field_claims(
            [
                raw_claim("monthly_rent", 18000, "Rent $18,000"),
                raw_claim(
                    "monthly_rent",
                    20000,
                    "Budget estimate suggests $20,000",
                    source_type="note",
                    claim_kind="inferred",
                    confidence="low",
                ),
            ],
            sources,
        )
        fact = next(fact for fact in merge_field_claims(verified) if fact.field_key == "monthly_rent")
        self.assertEqual(fact.system_state, "explicit")
        self.assertEqual(fact.system_value, 18000)
        self.assertEqual(fact.system_confidence, "high")
        self.assertEqual(len(fact.evidence), 2)

    def test_matching_explicit_claims_use_conservative_confidence(self):
        sources = (
            CandidateEvidenceSource("listing", "Rent $18,000"),
            CandidateEvidenceSource("chat", "Confirmed rent $18,000"),
        )
        verified = verify_field_claims(
            [
                raw_claim("monthly_rent", 18000, "Rent $18,000"),
                raw_claim(
                    "monthly_rent",
                    18000.0,
                    "Confirmed rent $18,000",
                    source_type="chat",
                    confidence="medium",
                ),
            ],
            sources,
        )
        fact = next(fact for fact in merge_field_claims(verified) if fact.field_key == "monthly_rent")
        self.assertEqual(fact.system_state, "explicit")
        self.assertEqual(fact.system_value, 18000)
        self.assertEqual(fact.system_confidence, "medium")

    def test_conflicting_inferences_are_conflicted_not_decision_usable(self):
        sources = (CandidateEvidenceSource("note", "Could be Wan Chai or Causeway Bay"),)
        verified = verify_field_claims(
            [
                raw_claim(
                    "district",
                    "Wan Chai",
                    "Could be Wan Chai",
                    source_type="note",
                    claim_kind="inferred",
                    confidence="low",
                ),
                raw_claim(
                    "district",
                    "Causeway Bay",
                    "Causeway Bay",
                    source_type="note",
                    claim_kind="inferred",
                    confidence="low",
                ),
            ],
            sources,
        )
        fact = next(fact for fact in merge_field_claims(verified) if fact.field_key == "district")
        self.assertEqual(fact.system_state, "conflicted")
        self.assertIsNone(fact.system_value)
        self.assertEqual(fact.system_confidence, "low")

    def test_image_claim_requires_matching_asset_id(self):
        asset_id = uuid.uuid4()
        other_asset_id = uuid.uuid4()
        sources = (
            CandidateEvidenceSource(
                "image_ocr",
                "差餉已包",
                source_asset_id=asset_id,
            ),
        )
        verified = verify_field_claims(
            [
                raw_claim(
                    "rates_included",
                    True,
                    "差餉已包",
                    source_type="image_ocr",
                    source_asset_id=str(other_asset_id),
                ),
                raw_claim(
                    "rates_included",
                    True,
                    "差餉已包",
                    source_type="image_ocr",
                    source_asset_id=str(asset_id),
                ),
            ],
            sources,
        )
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0].source_asset_id, asset_id)
