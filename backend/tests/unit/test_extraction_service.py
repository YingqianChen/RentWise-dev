from __future__ import annotations

import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.extraction_service import ExtractionService, normalize_raw_facts
from tests.helpers import build_candidate, build_project, build_user


class ExtractionServiceTests(IsolatedAsyncioTestCase):
    async def test_extract_normalizes_decision_signals_and_builds_source_aware_prompt(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        candidate.raw_listing_text = "5 mins walk CityU. Rent $5900."
        candidate.raw_chat_text = "Share with one person only. Give holding money now."
        candidate.raw_note_text = "Agent is pushy. Photos distorted."

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value={
                "monthly_rent": "$5900",
                "management_fee_amount": "unknown",
                "management_fee_included": "unknown",
                "rates_amount": "unknown",
                "rates_included": "unknown",
                "deposit": "2 months",
                "agent_fee": "half month less $200",
                "lease_term": "2 years",
                "move_in_date": "available now",
                "repair_responsibility": "unknown",
                "district": "Shek Kip Mei",
                "furnished": "unknown",
                "size_sqft": "unknown",
                "bedrooms": "room",
                "suspected_sdu": "unknown",
                "sdu_detection_reason": "unknown",
                "decision_signals": [
                    {
                        "key": "bathroom_sharing",
                        "category": "living arrangement",
                        "label": "Shared bathroom",
                        "source": "chat",
                        "evidence": "Share with one person only.",
                        "note": "Privacy may be lower than expected.",
                    },
                    {
                        "key": "holding_fee_risk",
                        "category": "trust",
                        "label": "Holding money refund is unclear",
                        "source": "chat",
                        "evidence": "Give holding money now. Maybe refund later.",
                        "note": None,
                    },
                ],
            },
        ) as completion:
            extracted = await ExtractionService().extract(candidate)

        prompt = completion.await_args.kwargs["prompt"]
        self.assertIn("[Listing]", prompt)
        self.assertIn("[Chat]", prompt)
        self.assertIn("[Notes]", prompt)
        self.assertEqual(extracted.monthly_rent, "$5900")
        self.assertEqual(len(extracted.decision_signals), 2)
        self.assertEqual(extracted.decision_signals[0]["category"], "living_arrangement")
        self.assertEqual(extracted.decision_signals[1]["source"], "chat")

    async def test_extract_preserves_english_location_fields(self):
        user = build_user()
        project = build_project(user)
        candidate = build_candidate(project)
        candidate.raw_listing_text = (
            "2-bedroom flat in City One Shatin, 400 sqft. Monthly rent HKD 12000. "
            "Building: City One Shatin Phase 3. Near Sha Tin MTR station."
        )

        with patch(
            "app.services.extraction_service.chat_completion_json",
            return_value={
                "address_text": "unknown",
                "building_name": "City One Shatin Phase 3",
                "nearest_station": "Sha Tin MTR",
                "district": "Sha Tin",
                "location_confidence": "medium",
                "monthly_rent": "HKD 12000",
                "management_fee_amount": "unknown",
                "management_fee_included": "unknown",
                "rates_amount": "unknown",
                "rates_included": "unknown",
                "deposit": "unknown",
                "agent_fee": "unknown",
                "lease_term": "unknown",
                "move_in_date": "unknown",
                "repair_responsibility": "unknown",
                "furnished": "unknown",
                "size_sqft": "400",
                "bedrooms": "2",
                "suspected_sdu": "unknown",
                "sdu_detection_reason": "unknown",
                "decision_signals": [],
                "raw_facts": ["Lease has break clause after year 1", "unknown"],
            },
        ):
            extracted = await ExtractionService().extract(candidate)

        self.assertEqual(extracted.building_name, "City One Shatin Phase 3")
        self.assertEqual(extracted.nearest_station, "Sha Tin MTR")
        self.assertEqual(extracted.district, "Sha Tin")
        self.assertEqual(extracted.location_confidence, "medium")
        self.assertEqual(extracted.raw_facts, ["Lease has break clause after year 1"])

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
