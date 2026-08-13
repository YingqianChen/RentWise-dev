from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateSourceAsset
from app.services.analysis_errors import AnalysisError
from app.services.extraction_service import ExtractionService, normalize_raw_facts
from tests.helpers import build_candidate, build_project, build_user


def build_payload(
    field_claims: list[object] | None = None,
    **supplemental_overrides: object,
) -> dict[str, object]:
    supplemental = {
        "furnished": "unknown",
        "size_sqft": "unknown",
        "bedrooms": "unknown",
        "suspected_sdu": "unknown",
        "sdu_detection_reason": "unknown",
        "decision_signals": [],
        "raw_facts": [],
    }
    supplemental.update(supplemental_overrides)
    return {
        "field_claims": field_claims or [],
        "supplemental": supplemental,
    }


def claim(
    field_key: str,
    value: object,
    quote: str,
    *,
    source_type: str = "listing",
    source_asset_id: str | None = None,
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


class ExtractionServiceTests(IsolatedAsyncioTestCase):
    async def test_extract_verifies_claims_and_builds_stable_source_prompt(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.raw_listing_text = "5 mins walk CityU. Rent $5900."
        candidate.raw_chat_text = "Share with one person only. Give holding money now."
        candidate.raw_note_text = "Agent is pushy. Photos distorted."

        payload = build_payload(
            [
                claim("monthly_rent", 5900, "Rent $5900"),
                claim("district", "Shek Kip Mei", "5 mins walk CityU", claim_kind="inferred"),
            ],
            bedrooms="room",
            decision_signals=[
                {
                    "key": "bathroom_sharing",
                    "category": "living arrangement",
                    "label": "Shared bathroom",
                    "source": "chat",
                    "evidence": "Share with one person only.",
                    "note": "Privacy may be lower than expected.",
                }
            ],
        )
        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=payload,
        ) as completion:
            result = await ExtractionService().extract_with_evidence(candidate)

        prompt = completion.await_args.kwargs["prompt"]
        self.assertIn("[SOURCE listing]", prompt)
        self.assertIn("[SOURCE chat]", prompt)
        self.assertIn("[SOURCE note]", prompt)
        self.assertEqual(result.extracted_info.monthly_rent, "5900")
        self.assertEqual(result.extracted_info.district, "unknown")
        self.assertEqual(len(result.extracted_info.decision_signals), 1)
        facts = {fact.field_key: fact for fact in result.field_facts}
        self.assertEqual(facts["monthly_rent"].system_state, "explicit")
        self.assertEqual(facts["district"].system_state, "inferred")
        self.assertEqual(len(facts), 14)

    async def test_extract_preserves_each_image_as_its_own_source(self):
        candidate = build_candidate(build_project(build_user()))
        asset_id = uuid.uuid4()
        candidate.source_assets = [
            CandidateSourceAsset(
                id=asset_id,
                candidate_id=candidate.id,
                storage_provider="local",
                storage_key="candidate/image.png",
                original_filename="agent screenshot.png",
                ocr_status="succeeded",
                ocr_text="管理費每月 $1,200 另計",
            )
        ]
        payload = build_payload(
            [
                claim(
                    "management_fee_amount",
                    1200,
                    "管理費每月 $1,200",
                    source_type="image_ocr",
                    source_asset_id=str(asset_id),
                ),
                claim(
                    "management_fee_included",
                    False,
                    "另計",
                    source_type="image_ocr",
                    source_asset_id=str(asset_id),
                ),
            ]
        )

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=payload,
        ) as completion:
            result = await ExtractionService().extract_with_evidence(candidate)

        prompt = completion.await_args.kwargs["prompt"]
        self.assertIn(f"asset_id={asset_id}", prompt)
        facts = {fact.field_key: fact for fact in result.field_facts}
        self.assertEqual(facts["management_fee_amount"].system_value, 1200)
        self.assertIs(facts["management_fee_included"].system_value, False)
        self.assertEqual(result.extracted_info.ocr_texts, ["管理費每月 $1,200 另計"])

    async def test_extract_discards_claim_when_quote_is_not_in_named_source(self):
        candidate = build_candidate(build_project(build_user()))
        payload = build_payload([claim("monthly_rent", 9000, "Rent $9000")])

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=payload,
        ):
            result = await ExtractionService().extract_with_evidence(candidate)

        rent_fact = next(fact for fact in result.field_facts if fact.field_key == "monthly_rent")
        self.assertEqual(rent_fact.system_state, "unknown")
        self.assertIsNone(rent_fact.system_value)
        self.assertEqual(result.extracted_info.monthly_rent, "unknown")

    async def test_extract_keeps_conflicting_sources_out_of_legacy_snapshot(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.raw_listing_text = "Rent $18,000"
        candidate.raw_chat_text = "New rent is $19,000"
        payload = build_payload(
            [
                claim("monthly_rent", 18000, "Rent $18,000"),
                claim(
                    "monthly_rent",
                    19000,
                    "New rent is $19,000",
                    source_type="chat",
                ),
            ]
        )

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=payload,
        ):
            result = await ExtractionService().extract_with_evidence(candidate)

        rent_fact = next(fact for fact in result.field_facts if fact.field_key == "monthly_rent")
        self.assertEqual(rent_fact.system_state, "conflicted")
        self.assertIsNone(rent_fact.system_value)
        self.assertEqual(len(rent_fact.evidence), 2)
        self.assertEqual(result.extracted_info.monthly_rent, "unknown")

    async def test_extract_preserves_explicit_english_location_fields(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.raw_listing_text = (
            "2-bedroom flat in City One Shatin. Building: City One Shatin Phase 3. "
            "Near Sha Tin MTR station."
        )
        payload = build_payload(
            [
                claim("building_name", "City One Shatin Phase 3", "City One Shatin Phase 3"),
                claim("nearest_station", "Sha Tin MTR", "Sha Tin MTR"),
                claim("district", "Sha Tin", "City One Shatin"),
            ],
            size_sqft="400",
            bedrooms="2",
            raw_facts=["Lease has break clause after year 1", "unknown"],
        )

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=payload,
        ):
            extracted = await ExtractionService().extract(candidate)

        self.assertEqual(extracted.building_name, "City One Shatin Phase 3")
        self.assertEqual(extracted.nearest_station, "Sha Tin MTR")
        self.assertEqual(extracted.district, "Sha Tin")
        self.assertEqual(extracted.location_confidence, "medium")
        self.assertEqual(extracted.location_source, "listing")
        self.assertEqual(extracted.raw_facts, ["Lease has break clause after year 1"])

    async def test_extract_raises_configured_error_when_llm_key_is_missing(self):
        candidate = build_candidate(build_project(build_user()))

        with patch(
            "app.services.extraction_service.chat_completion_json",
            side_effect=ValueError("GROQ_API_KEY is required for Groq provider"),
        ):
            with self.assertRaises(AnalysisError) as exc_info:
                await ExtractionService().extract(candidate)

        self.assertEqual(exc_info.exception.code, "llm_not_configured")
        self.assertNotIn("GROQ_API_KEY", exc_info.exception.user_message)

    async def test_extract_maps_timeout_to_llm_unavailable(self):
        candidate = build_candidate(build_project(build_user()))

        with patch(
            "app.services.extraction_service.chat_completion_json",
            side_effect=TimeoutError("provider timed out"),
        ):
            with self.assertRaises(AnalysisError) as exc_info:
                await ExtractionService().extract(candidate)

        self.assertEqual(exc_info.exception.code, "llm_unavailable")
        self.assertTrue(exc_info.exception.retryable)

    async def test_extract_rejects_incomplete_model_payload(self):
        candidate = build_candidate(build_project(build_user()))

        with patch("app.services.extraction_service.chat_completion_json", return_value={}):
            with self.assertRaises(AnalysisError) as exc_info:
                await ExtractionService().extract(candidate)

        self.assertEqual(exc_info.exception.code, "invalid_model_output")

    async def test_extract_maps_malformed_json_to_invalid_model_output(self):
        candidate = build_candidate(build_project(build_user()))

        with patch(
            "app.services.extraction_service.chat_completion_json",
            side_effect=ValueError("Model response does not contain a valid JSON object."),
        ):
            with self.assertRaises(AnalysisError) as exc_info:
                await ExtractionService().extract(candidate)

        self.assertEqual(exc_info.exception.code, "invalid_model_output")

    async def test_extract_accepts_valid_all_unknown_payload(self):
        candidate = build_candidate(build_project(build_user()))

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value=build_payload(),
        ):
            result = await ExtractionService().extract_with_evidence(candidate)

        self.assertEqual(result.extracted_info.monthly_rent, "unknown")
        self.assertEqual(result.extracted_info.district, "unknown")
        self.assertTrue(all(fact.system_state == "unknown" for fact in result.field_facts))

    async def test_extract_does_not_treat_derived_combined_text_as_a_source(self):
        candidate = build_candidate(build_project(build_user()))
        candidate.raw_listing_text = None
        candidate.raw_chat_text = None
        candidate.raw_note_text = None
        candidate.combined_text = "Legacy merged text with no identifiable source"

        with self.assertRaises(AnalysisError) as exc_info:
            await ExtractionService().extract(candidate)

        self.assertEqual(exc_info.exception.code, "no_usable_text")

    def test_normalize_raw_facts_filters_noise(self):
        result = normalize_raw_facts(
            [
                "  building renovated in 2024  ",
                "",
                "unknown",
                None,
                "pet friendly, landlord confirmed in chat",
            ]
        )
        self.assertEqual(
            result,
            [
                "building renovated in 2024",
                "pet friendly, landlord confirmed in chat",
            ],
        )

    def test_normalize_raw_facts_rejects_non_list(self):
        self.assertEqual(normalize_raw_facts("a single string"), [])
        self.assertEqual(normalize_raw_facts(None), [])
