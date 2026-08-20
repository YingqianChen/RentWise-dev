"""Project effective candidate field facts into the legacy extracted snapshot."""

from __future__ import annotations

from collections.abc import Iterable

from ..db.models import CandidateExtractedInfo, CandidateFieldFact
from .candidate_field_registry import (
    CANDIDATE_FIELD_KEYS,
    effective_field_state,
    effective_field_value,
    is_decision_usable,
)


_BOOLEAN_FIELDS = {"management_fee_included", "rates_included"}
_LOCATION_FIELDS = ("address_text", "building_name", "nearest_station", "district")


def _legacy_value(fact: CandidateFieldFact) -> object | None:
    state = effective_field_state(fact.system_state, fact.user_action)
    if not is_decision_usable(state):
        return None
    return effective_field_value(
        system_value=fact.system_value,
        system_state=fact.system_state,
        user_action=fact.user_action,
        user_value=fact.user_value,
    )


def _as_legacy_column_value(field_key: str, value: object | None) -> object | None:
    if value is None or field_key in _BOOLEAN_FIELDS:
        return value
    return str(value)


class CandidateFieldProjectionService:
    """Update only the 14 core columns while preserving supplemental extraction data."""

    def project_user_overrides(
        self,
        *,
        extracted_info: CandidateExtractedInfo,
        facts: Iterable[CandidateFieldFact],
    ) -> CandidateExtractedInfo:
        """Apply existing user actions without blanking fresh system unknowns."""
        facts_by_key = {fact.field_key: fact for fact in facts}
        if set(facts_by_key) != set(CANDIDATE_FIELD_KEYS):
            raise ValueError("User override projection requires all 14 core facts.")

        location_changed = False
        for field_key, fact in facts_by_key.items():
            if fact.user_action is None:
                continue
            setattr(extracted_info, field_key, _as_legacy_column_value(field_key, _legacy_value(fact)))
            location_changed = location_changed or field_key in _LOCATION_FIELDS

        if location_changed:
            self._project_location_metadata(extracted_info, facts_by_key)
        return extracted_info

    def project(
        self,
        *,
        extracted_info: CandidateExtractedInfo,
        facts: Iterable[CandidateFieldFact],
    ) -> CandidateExtractedInfo:
        facts_by_key = {fact.field_key: fact for fact in facts}
        if set(facts_by_key) != set(CANDIDATE_FIELD_KEYS):
            raise ValueError("Candidate field projection requires all 14 core facts.")

        for field_key in CANDIDATE_FIELD_KEYS:
            setattr(
                extracted_info,
                field_key,
                _as_legacy_column_value(field_key, _legacy_value(facts_by_key[field_key])),
            )

        self._project_location_metadata(extracted_info, facts_by_key)
        return extracted_info

    def _project_location_metadata(
        self,
        extracted_info: CandidateExtractedInfo,
        facts_by_key: dict[str, CandidateFieldFact],
    ) -> None:
        usable_keys = [
            field_key
            for field_key in _LOCATION_FIELDS
            if _legacy_value(facts_by_key[field_key]) is not None
        ]
        if "address_text" in usable_keys:
            extracted_info.location_confidence = "high"
        elif "building_name" in usable_keys or "nearest_station" in usable_keys:
            extracted_info.location_confidence = "medium"
        elif "district" in usable_keys:
            extracted_info.location_confidence = "low"
        else:
            extracted_info.location_confidence = "unknown"
            extracted_info.location_source = "unknown"
            return

        user_actions = {
            facts_by_key[field_key].user_action
            for field_key in usable_keys
            if facts_by_key[field_key].user_action is not None
        }
        if "corrected" in user_actions:
            extracted_info.location_source = "user_corrected"
            return
        if "confirmed" in user_actions:
            extracted_info.location_source = "user_confirmed"
            return

        source_types = {
            evidence.source_type
            for field_key in usable_keys
            for evidence in facts_by_key[field_key].evidence
            if evidence.claim_kind == "explicit"
        }
        extracted_info.location_source = (
            next(iter(source_types)) if len(source_types) == 1 else "mixed"
        )
