from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateFieldEvidence, CandidateFieldFact
from app.services.candidate_field_projection_service import CandidateFieldProjectionService
from app.services.candidate_field_registry import CANDIDATE_FIELD_KEYS
from tests.helpers import build_candidate, build_project, build_user


def build_facts(candidate_id) -> list[CandidateFieldFact]:
    return [
        CandidateFieldFact(
            candidate_id=candidate_id,
            field_key=field_key,
            system_value=None,
            system_state="unknown",
            system_confidence="low",
        )
        for field_key in CANDIDATE_FIELD_KEYS
    ]


class CandidateFieldProjectionServiceTests(TestCase):
    def test_projection_uses_only_explicit_or_user_values(self):
        candidate = build_candidate(build_project(build_user()))
        facts = build_facts(candidate.id)
        facts_by_key = {fact.field_key: fact for fact in facts}
        facts_by_key["monthly_rent"].system_value = 18000
        facts_by_key["monthly_rent"].system_state = "explicit"
        facts_by_key["monthly_rent"].system_confidence = "high"
        facts_by_key["deposit"].system_value = "2 months"
        facts_by_key["deposit"].system_state = "inferred"
        facts_by_key["district"].system_value = "Wan Chai"
        facts_by_key["district"].system_state = "inferred"
        facts_by_key["district"].user_action = "confirmed"
        facts_by_key["district"].user_value = "Wan Chai"

        CandidateFieldProjectionService().project(
            extracted_info=candidate.extracted_info,
            facts=facts,
        )

        self.assertEqual(candidate.extracted_info.monthly_rent, "18000")
        self.assertIsNone(candidate.extracted_info.deposit)
        self.assertEqual(candidate.extracted_info.district, "Wan Chai")
        self.assertEqual(candidate.extracted_info.location_confidence, "low")
        self.assertEqual(candidate.extracted_info.location_source, "user_confirmed")
        self.assertEqual(candidate.extracted_info.furnished, "furnished")

    def test_user_marked_unknown_removes_system_value_from_snapshot(self):
        candidate = build_candidate(build_project(build_user()))
        facts = build_facts(candidate.id)
        rent = next(fact for fact in facts if fact.field_key == "monthly_rent")
        rent.system_value = 18000
        rent.system_state = "explicit"
        rent.user_action = "marked_unknown"

        CandidateFieldProjectionService().project(
            extracted_info=candidate.extracted_info,
            facts=facts,
        )

        self.assertIsNone(candidate.extracted_info.monthly_rent)

    def test_system_location_source_comes_from_verified_evidence(self):
        candidate = build_candidate(build_project(build_user()))
        facts = build_facts(candidate.id)
        building = next(fact for fact in facts if fact.field_key == "building_name")
        building.system_value = "City One"
        building.system_state = "explicit"
        building.evidence.append(
            CandidateFieldEvidence(
                candidate_id=candidate.id,
                field_key="building_name",
                source_type="listing",
                quote="City One",
                claim_value="City One",
                claim_kind="explicit",
                confidence="high",
            )
        )

        CandidateFieldProjectionService().project(
            extracted_info=candidate.extracted_info,
            facts=facts,
        )

        self.assertEqual(candidate.extracted_info.location_source, "listing")

    def test_projection_requires_complete_field_set(self):
        candidate = build_candidate(build_project(build_user()))
        with self.assertRaises(ValueError):
            CandidateFieldProjectionService().project(
                extracted_info=candidate.extracted_info,
                facts=build_facts(candidate.id)[:-1],
            )
