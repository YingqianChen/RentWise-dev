"""Read helpers for the frozen candidate field contract."""

from __future__ import annotations

from collections.abc import Iterable

from ..db.models import CandidateFieldFact, CandidateListing
from .candidate_field_registry import (
    CANDIDATE_FIELD_KEYS,
    effective_field_state,
    effective_field_value,
    is_decision_usable,
)


def field_facts_by_key(
    candidate_or_facts: CandidateListing | Iterable[CandidateFieldFact],
) -> dict[str, CandidateFieldFact]:
    """Return one current fact per core field."""
    facts = (
        candidate_or_facts.field_facts
        if isinstance(candidate_or_facts, CandidateListing)
        else candidate_or_facts
    )
    return {fact.field_key: fact for fact in facts}


def has_complete_field_contract(candidate: CandidateListing) -> bool:
    """Return whether this candidate has exactly the frozen 14 core facts."""
    return (
        len(candidate.field_facts) == len(CANDIDATE_FIELD_KEYS)
        and set(field_facts_by_key(candidate)) == set(CANDIDATE_FIELD_KEYS)
    )


def candidate_field_state(candidate: CandidateListing, field_key: str) -> str | None:
    """Return the effective state for a field, or None for legacy/incomplete data."""
    fact = field_facts_by_key(candidate).get(field_key)
    if fact is None:
        return None
    return effective_field_state(fact.system_state, fact.user_action)


def candidate_field_value(candidate: CandidateListing, field_key: str) -> object | None:
    """Return a value only when its effective state may influence decisions."""
    fact = field_facts_by_key(candidate).get(field_key)
    if fact is None:
        return None
    state = effective_field_state(fact.system_state, fact.user_action)
    if not is_decision_usable(state):
        return None
    return effective_field_value(
        system_value=fact.system_value,
        system_state=fact.system_state,
        user_action=fact.user_action,
        user_value=fact.user_value,
    )


def field_needs_confirmation(candidate: CandidateListing, field_key: str) -> bool:
    """Return whether a field is absent, inferred, conflicted, or unknown."""
    state = candidate_field_state(candidate, field_key)
    return state is None or not is_decision_usable(state)
