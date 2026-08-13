from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_field_registry import (
    CANDIDATE_FIELD_DEFINITIONS,
    CANDIDATE_FIELD_KEYS,
    CandidateFieldValueError,
    effective_field_state,
    effective_field_value,
    is_decision_usable,
    validate_field_value,
)


class CandidateFieldRegistryTests(TestCase):
    def test_registry_freezes_fourteen_ordered_core_fields(self) -> None:
        self.assertEqual(
            CANDIDATE_FIELD_KEYS,
            (
                "monthly_rent",
                "management_fee_amount",
                "management_fee_included",
                "rates_amount",
                "rates_included",
                "deposit",
                "agent_fee",
                "lease_term",
                "move_in_date",
                "repair_responsibility",
                "district",
                "address_text",
                "building_name",
                "nearest_station",
            ),
        )
        self.assertEqual(len(CANDIDATE_FIELD_DEFINITIONS), 14)
        self.assertEqual(
            {definition.group for definition in CANDIDATE_FIELD_DEFINITIONS},
            {"monthly_cost", "move_in_and_lease", "repairs_and_timing", "location"},
        )

    def test_money_values_are_normalized_and_boolean_is_rejected(self) -> None:
        self.assertEqual(validate_field_value("monthly_rent", 18_000), 18_000)
        self.assertEqual(validate_field_value("monthly_rent", 18_000.5), 18_000.5)

        for invalid in (True, -1, math.inf, "18000"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(CandidateFieldValueError):
                    validate_field_value("monthly_rent", invalid)

    def test_boolean_and_text_values_are_strictly_validated(self) -> None:
        self.assertIs(validate_field_value("rates_included", False), False)
        self.assertEqual(validate_field_value("lease_term", "  two years  "), "two years")

        with self.assertRaises(CandidateFieldValueError):
            validate_field_value("rates_included", 0)
        with self.assertRaises(CandidateFieldValueError):
            validate_field_value("lease_term", "   ")
        with self.assertRaises(CandidateFieldValueError):
            validate_field_value("not_a_field", "value")

    def test_none_is_only_allowed_for_system_unknowns(self) -> None:
        self.assertIsNone(validate_field_value("deposit", None, allow_none=True))
        with self.assertRaises(CandidateFieldValueError):
            validate_field_value("deposit", None)

    def test_effective_state_keeps_system_and_user_meanings_separate(self) -> None:
        self.assertEqual(effective_field_state("explicit", None), "explicit")
        self.assertEqual(effective_field_state("inferred", "confirmed"), "user_confirmed")
        self.assertEqual(effective_field_state("conflicted", "corrected"), "user_corrected")
        self.assertEqual(effective_field_state("explicit", "marked_unknown"), "user_marked_unknown")

    def test_only_explicit_or_user_values_are_decision_usable(self) -> None:
        expected = {
            "explicit": True,
            "inferred": False,
            "conflicted": False,
            "unknown": False,
            "user_confirmed": True,
            "user_corrected": True,
            "user_marked_unknown": False,
        }
        self.assertEqual(
            {state: is_decision_usable(state) for state in expected},
            expected,
        )

    def test_effective_value_prefers_snapshotted_user_value(self) -> None:
        self.assertEqual(
            effective_field_value(
                system_value=19000,
                system_state="explicit",
                user_action="confirmed",
                user_value=18000,
            ),
            18000,
        )
        self.assertIsNone(
            effective_field_value(
                system_value=19000,
                system_state="explicit",
                user_action="marked_unknown",
                user_value=None,
            )
        )
