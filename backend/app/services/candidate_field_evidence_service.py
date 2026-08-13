"""Verify, merge, and persist source-backed candidate field claims."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CandidateFieldEvidence, CandidateFieldFact
from .candidate_field_registry import (
    CANDIDATE_FIELD_KEYS,
    FIELD_CLAIM_KINDS,
    FIELD_CONFIDENCE_LEVELS,
    FIELD_SOURCE_TYPES,
    CandidateFieldValueError,
    validate_field_value,
)


@dataclass(frozen=True, slots=True)
class CandidateEvidenceSource:
    """One independently identifiable source supplied to extraction."""

    source_type: str
    text: str
    source_asset_id: UUID | None = None
    filename: str | None = None


@dataclass(frozen=True, slots=True)
class VerifiedFieldClaim:
    """A model claim whose value and quote both passed local validation."""

    field_key: str
    value: object
    source_type: str
    source_asset_id: UUID | None
    quote: str
    claim_kind: str
    confidence: str


@dataclass(frozen=True, slots=True)
class MergedFieldFact:
    """Deterministic system result for one core field."""

    field_key: str
    system_value: object | None
    system_state: str
    system_confidence: str
    evidence: tuple[VerifiedFieldClaim, ...]


_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(
        str.maketrans(
            {
                "‘": "'",
                "’": "'",
                "“": '"',
                "”": '"',
                "–": "-",
                "—": "-",
                "−": "-",
                "，": ",",
                "。": ".",
                "：": ":",
                "；": ";",
            }
        )
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _quote_exists_in_source(quote: str, source_text: str) -> bool:
    normalized_quote = _normalized_text(quote)
    return bool(normalized_quote) and normalized_quote in _normalized_text(source_text)


def _value_identity(value: object) -> tuple[str, object]:
    if isinstance(value, str):
        return ("text", _normalized_text(value))
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", float(value))
    return (type(value).__name__, repr(value))


def verify_field_claims(
    raw_claims: list[object],
    sources: tuple[CandidateEvidenceSource, ...],
) -> tuple[VerifiedFieldClaim, ...]:
    """Discard unsupported individual claims without accepting invented evidence."""
    source_map = {
        (source.source_type, source.source_asset_id): source
        for source in sources
    }
    verified: list[VerifiedFieldClaim] = []
    seen: set[tuple[object, ...]] = set()

    for raw_claim in raw_claims:
        if not isinstance(raw_claim, dict):
            continue

        field_key = raw_claim.get("field_key")
        source_type = raw_claim.get("source_type")
        claim_kind = raw_claim.get("claim_kind")
        confidence = raw_claim.get("confidence")
        quote = raw_claim.get("quote")
        raw_asset_id = raw_claim.get("source_asset_id")

        if (
            field_key not in CANDIDATE_FIELD_KEYS
            or source_type not in FIELD_SOURCE_TYPES
            or claim_kind not in FIELD_CLAIM_KINDS
            or confidence not in FIELD_CONFIDENCE_LEVELS
            or not isinstance(quote, str)
        ):
            continue

        source_asset_id: UUID | None = None
        if source_type == "image_ocr":
            try:
                source_asset_id = UUID(str(raw_asset_id))
            except (TypeError, ValueError):
                continue
        elif raw_asset_id is not None:
            continue

        source = source_map.get((source_type, source_asset_id))
        if source is None or not _quote_exists_in_source(quote, source.text):
            continue

        try:
            value = validate_field_value(field_key, raw_claim.get("value"))
        except CandidateFieldValueError:
            continue

        identity = (
            field_key,
            _value_identity(value),
            source_type,
            source_asset_id,
            _normalized_text(quote),
            claim_kind,
        )
        if identity in seen:
            continue
        seen.add(identity)
        verified.append(
            VerifiedFieldClaim(
                field_key=field_key,
                value=value,
                source_type=source_type,
                source_asset_id=source_asset_id,
                quote=quote.strip(),
                claim_kind=claim_kind,
                confidence=confidence,
            )
        )

    return tuple(verified)


def merge_field_claims(claims: tuple[VerifiedFieldClaim, ...]) -> tuple[MergedFieldFact, ...]:
    """Resolve verified claims into the four frozen system states."""
    claims_by_field = {field_key: [] for field_key in CANDIDATE_FIELD_KEYS}
    for claim in claims:
        claims_by_field[claim.field_key].append(claim)

    merged: list[MergedFieldFact] = []
    for field_key in CANDIDATE_FIELD_KEYS:
        field_claims = claims_by_field[field_key]
        explicit_claims = [claim for claim in field_claims if claim.claim_kind == "explicit"]
        selected_claims = explicit_claims or field_claims

        if not selected_claims:
            merged.append(
                MergedFieldFact(
                    field_key=field_key,
                    system_value=None,
                    system_state="unknown",
                    system_confidence="low",
                    evidence=tuple(field_claims),
                )
            )
            continue

        values_by_identity: dict[tuple[str, object], object] = {}
        for claim in selected_claims:
            values_by_identity.setdefault(_value_identity(claim.value), claim.value)

        if len(values_by_identity) > 1:
            merged.append(
                MergedFieldFact(
                    field_key=field_key,
                    system_value=None,
                    system_state="conflicted",
                    system_confidence="low",
                    evidence=tuple(field_claims),
                )
            )
            continue

        confidence = min(
            selected_claims,
            key=lambda claim: _CONFIDENCE_RANK[claim.confidence],
        ).confidence
        merged.append(
            MergedFieldFact(
                field_key=field_key,
                system_value=next(iter(values_by_identity.values())),
                system_state="explicit" if explicit_claims else "inferred",
                system_confidence=confidence,
                evidence=tuple(field_claims),
            )
        )

    return tuple(merged)


class CandidateFieldEvidenceService:
    """Persist fresh system results while retaining future user overrides."""

    async def replace_system_results(
        self,
        db: AsyncSession,
        *,
        candidate_id: UUID,
        facts: tuple[MergedFieldFact, ...],
    ) -> None:
        result = await db.execute(
            select(CandidateFieldFact).where(CandidateFieldFact.candidate_id == candidate_id)
        )
        existing_by_key = {fact.field_key: fact for fact in result.scalars().all()}

        await db.execute(
            delete(CandidateFieldEvidence).where(
                CandidateFieldEvidence.candidate_id == candidate_id
            )
        )

        for merged_fact in facts:
            fact = existing_by_key.get(merged_fact.field_key)
            if fact is None:
                fact = CandidateFieldFact(
                    candidate_id=candidate_id,
                    field_key=merged_fact.field_key,
                    system_value=merged_fact.system_value,
                    system_state=merged_fact.system_state,
                    system_confidence=merged_fact.system_confidence,
                )
                db.add(fact)
            else:
                fact.system_value = merged_fact.system_value
                fact.system_state = merged_fact.system_state
                fact.system_confidence = merged_fact.system_confidence

        await db.flush()

        db.add_all(
            CandidateFieldEvidence(
                candidate_id=candidate_id,
                field_key=claim.field_key,
                source_type=claim.source_type,
                source_asset_id=claim.source_asset_id,
                quote=claim.quote,
                claim_value=claim.value,
                claim_kind=claim.claim_kind,
                confidence=claim.confidence,
            )
            for merged_fact in facts
            for claim in merged_fact.evidence
        )
