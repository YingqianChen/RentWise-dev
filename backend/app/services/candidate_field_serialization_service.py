"""Serialize candidate field facts in the frozen product order."""

from __future__ import annotations

from ..db.models import CandidateFieldEvidence, CandidateFieldFact
from ..schemas.candidate import CandidateFieldEvidenceResponse, CandidateFieldFactResponse
from .candidate_field_registry import (
    CANDIDATE_FIELD_DEFINITIONS,
    effective_field_state,
    effective_field_value,
    is_decision_usable,
)


def _source_label(evidence: CandidateFieldEvidence) -> str:
    if evidence.source_type == "listing":
        return "Listing text"
    if evidence.source_type == "chat":
        return "Chat"
    if evidence.source_type == "note":
        return "Note"
    if evidence.source_asset is not None:
        return evidence.source_asset.original_filename
    return "Image OCR"


def serialize_candidate_field_facts(
    facts: list[CandidateFieldFact],
) -> list[CandidateFieldFactResponse]:
    facts_by_key = {fact.field_key: fact for fact in facts}
    serialized: list[CandidateFieldFactResponse] = []
    for definition in CANDIDATE_FIELD_DEFINITIONS:
        fact = facts_by_key.get(definition.key)
        if fact is None:
            continue
        state = effective_field_state(fact.system_state, fact.user_action)
        value = effective_field_value(
            system_value=fact.system_value,
            system_state=fact.system_state,
            user_action=fact.user_action,
            user_value=fact.user_value,
        )
        serialized.append(
            CandidateFieldFactResponse(
                key=fact.field_key,
                label=definition.label,
                group=definition.group,
                value=value,
                state=state,
                confidence=fact.system_confidence,
                decision_usable=is_decision_usable(state),
                system_value=fact.system_value,
                system_state=fact.system_state,
                system_confidence=fact.system_confidence,
                user_action=fact.user_action,
                user_note=fact.user_note,
                user_updated_at=fact.user_updated_at,
                evidence=[
                    CandidateFieldEvidenceResponse(
                        id=evidence.id,
                        source_type=evidence.source_type,
                        source_asset_id=evidence.source_asset_id,
                        source_label=_source_label(evidence),
                        quote=evidence.quote,
                        claim_value=evidence.claim_value,
                        claim_kind=evidence.claim_kind,
                        confidence=evidence.confidence,
                    )
                    for evidence in fact.evidence
                ],
            )
        )
    return serialized
