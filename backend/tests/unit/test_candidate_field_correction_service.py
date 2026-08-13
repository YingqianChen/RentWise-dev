from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateFieldFact, CandidateFieldRevision
from app.services.candidate_field_correction_service import (
    CandidateFieldCorrectionError,
    CandidateFieldCorrectionService,
)


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush = AsyncMock()

    def add(self, value: object) -> None:
        self.added.append(value)


def build_fact(
    *,
    field_key: str = "monthly_rent",
    system_value: object | None = 18000,
    system_state: str = "explicit",
) -> CandidateFieldFact:
    return CandidateFieldFact(
        candidate_id=uuid.uuid4(),
        field_key=field_key,
        system_value=system_value,
        system_state=system_state,
        system_confidence="high",
    )


class CandidateFieldCorrectionServiceTests(IsolatedAsyncioTestCase):
    async def test_confirm_snapshots_current_system_value(self):
        fact = build_fact()
        db = _FakeSession()

        await CandidateFieldCorrectionService().apply_to_fact(
            db,
            fact=fact,
            actor_user_id=uuid.uuid4(),
            action="confirm",
            value=None,
            note="Confirmed by phone",
        )

        self.assertEqual(fact.user_action, "confirmed")
        self.assertEqual(fact.user_value, 18000)
        fact.system_value = 19000
        self.assertEqual(fact.user_value, 18000)
        revision = db.added[0]
        self.assertIsInstance(revision, CandidateFieldRevision)
        self.assertEqual(revision.action, "confirm")
        self.assertEqual(revision.previous_value, 18000)
        self.assertEqual(revision.new_value, 18000)

    async def test_confirm_rejects_unknown_or_conflicted_system_result(self):
        for state in ("unknown", "conflicted"):
            with self.subTest(state=state):
                fact = build_fact(system_value=None, system_state=state)
                with self.assertRaises(CandidateFieldCorrectionError) as exc_info:
                    await CandidateFieldCorrectionService().apply_to_fact(
                        _FakeSession(),
                        fact=fact,
                        actor_user_id=uuid.uuid4(),
                        action="confirm",
                        value=None,
                        note=None,
                    )
                self.assertEqual(exc_info.exception.status_code, 409)

    async def test_correct_validates_typed_value(self):
        fact = build_fact(field_key="rates_included", system_value=True)
        with self.assertRaises(CandidateFieldCorrectionError) as exc_info:
            await CandidateFieldCorrectionService().apply_to_fact(
                _FakeSession(),
                fact=fact,
                actor_user_id=uuid.uuid4(),
                action="correct",
                value="yes",
                note=None,
            )

        self.assertIn("true or false", str(exc_info.exception))
        self.assertIsNone(fact.user_action)

    async def test_mark_unknown_and_revert_are_audited(self):
        fact = build_fact()
        db = _FakeSession()
        service = CandidateFieldCorrectionService()
        actor_id = uuid.uuid4()

        await service.apply_to_fact(
            db,
            fact=fact,
            actor_user_id=actor_id,
            action="mark_unknown",
            value=None,
            note="Waiting for agent",
        )
        self.assertEqual(fact.user_action, "marked_unknown")
        self.assertIsNone(fact.user_value)

        await service.apply_to_fact(
            db,
            fact=fact,
            actor_user_id=actor_id,
            action="revert",
            value=None,
            note=None,
        )
        self.assertIsNone(fact.user_action)
        self.assertIsNone(fact.user_note)
        self.assertIsNone(fact.user_updated_at)
        revisions = [item for item in db.added if isinstance(item, CandidateFieldRevision)]
        self.assertEqual([item.action for item in revisions], ["mark_unknown", "revert"])
        self.assertIsNone(revisions[0].new_value)
        self.assertEqual(revisions[1].new_value, 18000)

    async def test_revert_without_override_is_rejected(self):
        with self.assertRaises(CandidateFieldCorrectionError) as exc_info:
            await CandidateFieldCorrectionService().apply_to_fact(
                _FakeSession(),
                fact=build_fact(),
                actor_user_id=uuid.uuid4(),
                action="revert",
                value=None,
                note=None,
            )
        self.assertEqual(exc_info.exception.status_code, 409)
