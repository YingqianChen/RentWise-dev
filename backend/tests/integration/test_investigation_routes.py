from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import investigation as investigation_api
from app.db.models import InvestigationItem
from app.schemas.dashboard import InvestigationItemSummary
from app.schemas.investigation import InvestigationItemUpdate
from app.services.investigation_service import InvestigationService
from tests.helpers import build_project, build_user


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return [self.value] if self.value is not None else []


class _FakeSession:
    def __init__(self, result):
        self.result = result
        self.flush = AsyncMock()
        self.refresh = AsyncMock()

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(self.result)


class InvestigationRouteTests(IsolatedAsyncioTestCase):
    async def test_user_can_update_owned_investigation_item_status_and_note(self):
        user = build_user()
        project = build_project(user)
        item = InvestigationItem(
            id=uuid.uuid4(),
            project_id=project.id,
            candidate_id=None,
            category="cost",
            title="Confirm the quoted rent",
            question="Ask for the rent in writing.",
            priority="high",
            status="open",
        )
        db = _FakeSession(item)

        async def fake_get_project_for_user(project_id, current_user, session):
            self.assertEqual(project_id, project.id)
            self.assertEqual(current_user.id, user.id)
            self.assertIs(session, db)
            return project

        with patch.object(investigation_api, "get_project_for_user", fake_get_project_for_user):
            response = await investigation_api.update_investigation_item(
                project_id=project.id,
                item_id=item.id,
                item_data=InvestigationItemUpdate(
                    status="resolved",
                    note="Landlord confirmed this in WhatsApp.",
                ),
                current_user=user,
                db=db,
            )

        self.assertEqual(response.status, "resolved")
        self.assertEqual(response.note, "Landlord confirmed this in WhatsApp.")
        self.assertEqual(item.status, "resolved")
        self.assertEqual(item.note, "Landlord confirmed this in WhatsApp.")
        db.flush.assert_awaited_once()

    async def test_sync_preserves_user_progress_and_separates_closed_items(self):
        user = build_user()
        project = build_project(user)
        item_id = uuid.uuid4()
        existing = InvestigationItem(
            id=item_id,
            project_id=project.id,
            candidate_id=None,
            category="clause",
            title="Old wording",
            question="Old question",
            priority="medium",
            status="dismissed",
            note="Not relevant for this listing.",
        )
        db = _FakeSession(existing)
        generated = InvestigationItemSummary(
            id=item_id,
            candidate_id=None,
            category="clause",
            title="Updated wording",
            question="Updated question",
            priority="high",
            status="open",
        )

        open_items, closed_items = await InvestigationService().sync_items(
            db=db,
            project=project,
            generated_items=[generated],
        )

        self.assertEqual(open_items, [])
        self.assertEqual(len(closed_items), 1)
        self.assertEqual(closed_items[0].status, "dismissed")
        self.assertEqual(closed_items[0].note, "Not relevant for this listing.")
        self.assertEqual(existing.title, "Updated wording")
        self.assertEqual(existing.priority, "high")
        db.flush.assert_awaited_once()

    async def test_update_rejects_item_from_another_project(self):
        user = build_user()
        project = build_project(user)
        db = _FakeSession(None)

        async def fake_get_project_for_user(*_args, **_kwargs):
            return project

        with patch.object(investigation_api, "get_project_for_user", fake_get_project_for_user):
            with self.assertRaises(investigation_api.HTTPException) as context:
                await investigation_api.update_investigation_item(
                    project_id=project.id,
                    item_id=uuid.uuid4(),
                    item_data=InvestigationItemUpdate(status="open"),
                    current_user=user,
                    db=db,
                )

        self.assertEqual(context.exception.status_code, 404)
