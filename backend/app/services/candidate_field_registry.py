"""Frozen field contract for candidate facts and evidence."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, TypeAlias


FieldValueType: TypeAlias = Literal["money", "boolean", "text"]
FieldGroup: TypeAlias = Literal[
    "monthly_cost",
    "move_in_and_lease",
    "repairs_and_timing",
    "location",
]
SystemFieldState: TypeAlias = Literal["explicit", "inferred", "conflicted", "unknown"]
UserFieldAction: TypeAlias = Literal["confirmed", "corrected", "marked_unknown"]
EffectiveFieldState: TypeAlias = Literal[
    "explicit",
    "inferred",
    "conflicted",
    "unknown",
    "user_confirmed",
    "user_corrected",
    "user_marked_unknown",
]

SYSTEM_FIELD_STATES = ("explicit", "inferred", "conflicted", "unknown")
USER_FIELD_ACTIONS = ("confirmed", "corrected", "marked_unknown")
EFFECTIVE_FIELD_STATES = (
    *SYSTEM_FIELD_STATES,
    "user_confirmed",
    "user_corrected",
    "user_marked_unknown",
)
DECISION_USABLE_STATES = frozenset({"explicit", "user_confirmed", "user_corrected"})
FIELD_CONFIDENCE_LEVELS = ("high", "medium", "low")
FIELD_SOURCE_TYPES = ("listing", "chat", "note", "image_ocr")
FIELD_CLAIM_KINDS = ("explicit", "inferred")
FIELD_REVISION_ACTIONS = ("confirm", "correct", "mark_unknown", "revert")


@dataclass(frozen=True, slots=True)
class CandidateFieldDefinition:
    key: str
    label: str
    value_type: FieldValueType
    group: FieldGroup
    max_length: int | None = None


CANDIDATE_FIELD_DEFINITIONS = (
    CandidateFieldDefinition("monthly_rent", "Monthly rent", "money", "monthly_cost"),
    CandidateFieldDefinition("management_fee_amount", "Management fee", "money", "monthly_cost"),
    CandidateFieldDefinition("management_fee_included", "Management fee included", "boolean", "monthly_cost"),
    CandidateFieldDefinition("rates_amount", "Rates amount", "money", "monthly_cost"),
    CandidateFieldDefinition("rates_included", "Rates included", "boolean", "monthly_cost"),
    CandidateFieldDefinition("deposit", "Deposit", "text", "move_in_and_lease", max_length=100),
    CandidateFieldDefinition("agent_fee", "Agent fee", "text", "move_in_and_lease", max_length=100),
    CandidateFieldDefinition("lease_term", "Lease term", "text", "move_in_and_lease", max_length=100),
    CandidateFieldDefinition("move_in_date", "Move-in date", "text", "repairs_and_timing", max_length=100),
    CandidateFieldDefinition(
        "repair_responsibility",
        "Repair responsibility",
        "text",
        "repairs_and_timing",
        max_length=255,
    ),
    CandidateFieldDefinition("district", "District", "text", "location", max_length=100),
    CandidateFieldDefinition("address_text", "Address", "text", "location", max_length=500),
    CandidateFieldDefinition("building_name", "Building name", "text", "location", max_length=255),
    CandidateFieldDefinition("nearest_station", "Nearest station", "text", "location", max_length=255),
)
CANDIDATE_FIELD_KEYS = tuple(definition.key for definition in CANDIDATE_FIELD_DEFINITIONS)
CANDIDATE_FIELD_BY_KEY = {definition.key: definition for definition in CANDIDATE_FIELD_DEFINITIONS}


class CandidateFieldValueError(ValueError):
    """Raised when a value does not satisfy the frozen field contract."""


def validate_field_value(field_key: str, value: object, *, allow_none: bool = False) -> object:
    """Validate and normalize a typed field value without doing I/O."""
    definition = CANDIDATE_FIELD_BY_KEY.get(field_key)
    if definition is None:
        raise CandidateFieldValueError(f"Unsupported candidate field: {field_key}")

    if value is None:
        if allow_none:
            return None
        raise CandidateFieldValueError(f"{field_key} requires a value")

    if definition.value_type == "money":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CandidateFieldValueError(f"{field_key} must be a number")
        if not math.isfinite(value) or value < 0:
            raise CandidateFieldValueError(f"{field_key} must be a finite non-negative number")
        return int(value) if float(value).is_integer() else float(value)

    if definition.value_type == "boolean":
        if not isinstance(value, bool):
            raise CandidateFieldValueError(f"{field_key} must be true or false")
        return value

    if not isinstance(value, str):
        raise CandidateFieldValueError(f"{field_key} must be text")
    normalized = value.strip()
    if not normalized:
        raise CandidateFieldValueError(f"{field_key} cannot be blank")
    if definition.max_length is not None and len(normalized) > definition.max_length:
        raise CandidateFieldValueError(
            f"{field_key} cannot exceed {definition.max_length} characters"
        )
    return normalized


def effective_field_state(
    system_state: SystemFieldState,
    user_action: UserFieldAction | None,
) -> EffectiveFieldState:
    """Resolve the user-facing state without mixing system and user decisions."""
    if system_state not in SYSTEM_FIELD_STATES:
        raise ValueError(f"Unsupported system field state: {system_state}")
    if user_action is None:
        return system_state
    if user_action not in USER_FIELD_ACTIONS:
        raise ValueError(f"Unsupported user field action: {user_action}")
    return {
        "confirmed": "user_confirmed",
        "corrected": "user_corrected",
        "marked_unknown": "user_marked_unknown",
    }[user_action]


def is_decision_usable(state: EffectiveFieldState) -> bool:
    """Return whether a field state may feed deterministic product decisions."""
    if state not in EFFECTIVE_FIELD_STATES:
        raise ValueError(f"Unsupported effective field state: {state}")
    return state in DECISION_USABLE_STATES


def effective_field_value(
    *,
    system_value: object | None,
    system_state: SystemFieldState,
    user_action: UserFieldAction | None,
    user_value: object | None,
) -> object | None:
    """Resolve the displayed field value without mutating either source of truth."""
    state = effective_field_state(system_state, user_action)
    if state in {"user_confirmed", "user_corrected"}:
        return user_value
    if state == "user_marked_unknown":
        return None
    return system_value
