"""Apply auditable user actions to one candidate field fact."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.database import utc_now
from ..db.models import (
    CandidateCommuteEvidence,
    CandidateFieldFact,
    CandidateFieldRevision,
    CandidateListing,
    SearchProject,
)
from .candidate_analysis_state import has_usable_analysis
from .candidate_field_projection_service import CandidateFieldProjectionService
from .candidate_field_registry import (
    CANDIDATE_FIELD_BY_KEY,
    CANDIDATE_FIELD_KEYS,
    CandidateFieldValueError,
    effective_field_value,
    validate_field_value,
)

if TYPE_CHECKING:
    from .candidate_pipeline_service import CandidatePipelineService


_LOCATION_FIELD_KEYS = {"district", "address_text", "building_name", "nearest_station"}


@dataclass(frozen=True, slots=True)
class CandidateFieldAction:
    field_key: str
    action: str
    value: object | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateFieldCorrectionError(ValueError):
    """A user-correctable field action error with an API-safe status."""

    message: str
    status_code: int = 422

    def __str__(self) -> str:
        return self.message


class CandidateFieldCorrectionService:
    """Mutate the user-owned columns and append one revision in the same transaction."""

    def __init__(self) -> None:
        self.projection_service = CandidateFieldProjectionService()

    async def apply_candidate_actions(
        self,
        db: AsyncSession,
        *,
        project: SearchProject,
        candidate: CandidateListing,
        actor_user_id: UUID,
        actions: list[CandidateFieldAction],
        pipeline: CandidatePipelineService,
    ) -> None:
        if not has_usable_analysis(candidate):
            raise CandidateFieldCorrectionError(
                "Candidate analysis must complete before editing field facts.",
                status_code=409,
            )

        locked_result = await db.execute(
            select(CandidateFieldFact)
            .options(selectinload(CandidateFieldFact.evidence))
            .where(CandidateFieldFact.candidate_id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_facts = list(locked_result.scalars().all())
        facts_by_key = {fact.field_key: fact for fact in locked_facts}
        if set(facts_by_key) != set(CANDIDATE_FIELD_KEYS):
            raise CandidateFieldCorrectionError(
                "This candidate needs to be reassessed before editing field facts.",
                status_code=409,
            )

        location_changed = False
        for action in actions:
            if action.field_key not in CANDIDATE_FIELD_BY_KEY:
                raise CandidateFieldCorrectionError(
                    f"Unsupported candidate field: {action.field_key}"
                )
            await self.apply_to_fact(
                db,
                fact=facts_by_key[action.field_key],
                actor_user_id=actor_user_id,
                action=action.action,
                value=action.value,
                note=action.note,
            )
            location_changed = location_changed or action.field_key in _LOCATION_FIELD_KEYS

        self.projection_service.project(
            extracted_info=candidate.extracted_info,
            facts=locked_facts,
        )
        if location_changed:
            await db.execute(
                delete(CandidateCommuteEvidence).where(
                    CandidateCommuteEvidence.candidate_id == candidate.id
                )
            )
        candidate.updated_at = utc_now()
        await pipeline.reassess_after_field_change(
            db=db,
            project=project,
            candidate=candidate,
        )
        await db.flush()

    async def apply_to_fact(
        self,
        db: AsyncSession,
        *,
        fact: CandidateFieldFact,
        actor_user_id: UUID,
        action: str,
        value: object | None,
        note: str | None,
    ) -> CandidateFieldFact:
        normalized_note = self._normalize_note(note)
        previous_value = self._effective_value(fact)
        now = datetime.now(timezone.utc)

        if action == "confirm":
            if value is not None:
                raise CandidateFieldCorrectionError("Confirm does not accept a replacement value.")
            if fact.system_state not in {"explicit", "inferred"} or fact.system_value is None:
                raise CandidateFieldCorrectionError(
                    "This field has no single system value to confirm.",
                    status_code=409,
                )
            fact.user_action = "confirmed"
            fact.user_value = fact.system_value
        elif action == "correct":
            try:
                fact.user_value = validate_field_value(fact.field_key, value)
            except CandidateFieldValueError as exc:
                raise CandidateFieldCorrectionError(str(exc)) from exc
            fact.user_action = "corrected"
        elif action == "mark_unknown":
            if value is not None:
                raise CandidateFieldCorrectionError("Mark unknown does not accept a value.")
            fact.user_action = "marked_unknown"
            fact.user_value = None
        elif action == "revert":
            if value is not None:
                raise CandidateFieldCorrectionError("Revert does not accept a value.")
            if fact.user_action is None:
                raise CandidateFieldCorrectionError(
                    "This field is already using the system result.",
                    status_code=409,
                )
            fact.user_action = None
            fact.user_value = None
        else:
            raise CandidateFieldCorrectionError("Unsupported field action.")

        fact.user_note = None if action == "revert" else normalized_note
        fact.user_updated_at = None if action == "revert" else now
        new_value = self._effective_value(fact)
        db.add(
            CandidateFieldRevision(
                candidate_id=fact.candidate_id,
                field_key=fact.field_key,
                actor_user_id=actor_user_id,
                action=action,
                previous_value=previous_value,
                new_value=new_value,
                note=normalized_note,
            )
        )
        await db.flush()
        return fact

    @staticmethod
    def _effective_value(fact: CandidateFieldFact) -> object | None:
        return effective_field_value(
            system_value=fact.system_value,
            system_state=fact.system_state,
            user_action=fact.user_action,
            user_value=fact.user_value,
        )

    @staticmethod
    def _normalize_note(note: str | None) -> str | None:
        if note is None:
            return None
        normalized = note.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise CandidateFieldCorrectionError("Field note cannot exceed 1000 characters.")
        return normalized
