from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from unittest import SkipTest, TestCase
from unittest.mock import AsyncMock, patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.db.models import (
    CandidateCommuteEvidence,
    CandidateFieldEvidence,
    CandidateFieldFact,
    CandidateFieldRevision,
    CandidateListing,
    SearchProject,
    User,
)
from app.main import app
from app.services.candidate_field_evidence_service import (
    CandidateFieldEvidenceService,
    VerifiedFieldClaim,
    merge_field_claims,
)


def _valid_extraction_payload() -> dict[str, object]:
    return {
        "field_claims": [
            {
                "field_key": "district",
                "value": "Wan Chai",
                "source_type": "listing",
                "source_asset_id": None,
                "quote": "Wan Chai",
                "claim_kind": "explicit",
                "confidence": "high",
            },
            {
                "field_key": "monthly_rent",
                "value": 18000,
                "source_type": "listing",
                "source_asset_id": None,
                "quote": "rent 18000",
                "claim_kind": "explicit",
                "confidence": "high",
            },
            {
                "field_key": "deposit",
                "value": "2 months",
                "source_type": "listing",
                "source_asset_id": None,
                "quote": "deposit 2 months",
                "claim_kind": "explicit",
                "confidence": "high",
            },
            {
                "field_key": "lease_term",
                "value": "2 years",
                "source_type": "listing",
                "source_asset_id": None,
                "quote": "lease 2 years",
                "claim_kind": "explicit",
                "confidence": "high",
            },
        ],
        "supplemental": {
            "furnished": "unknown",
            "size_sqft": "unknown",
            "bedrooms": "unknown",
            "suspected_sdu": "unknown",
            "sdu_detection_reason": "unknown",
            "decision_signals": [],
            "raw_facts": [],
        },
    }


def _all_unknown_extraction_payload() -> dict[str, object]:
    payload = _valid_extraction_payload()
    payload["field_claims"] = []
    return payload


class DatabaseFlowTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if os.getenv("RUN_DB_INTEGRATION") != "1":
            raise SkipTest("Set RUN_DB_INTEGRATION=1 to run real database integration tests.")

        database_name = make_url(settings.DATABASE_URL).database or ""
        if not database_name.endswith("_test"):
            raise RuntimeError(
                "Refusing to run database integration tests against a non-test database. "
                "DATABASE_URL must point to a database whose name ends with '_test'."
            )

        cls.alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(cls.alembic_cfg, "head")
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self) -> None:
        self.email = f"db-flow-{uuid.uuid4().hex[:12]}@example.com"
        self.other_email = f"other-{self.email}"

    def tearDown(self) -> None:
        asyncio.run(self._cleanup_user())

    async def _cleanup_user(self) -> None:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(
                delete(User).where(User.email.in_([self.email, self.other_email]))
            )
            await session.commit()
        await engine.dispose()

    async def _field_record_counts(self, candidate_id: uuid.UUID) -> tuple[int, int]:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            fact_count = await session.scalar(
                select(func.count())
                .select_from(CandidateFieldFact)
                .where(CandidateFieldFact.candidate_id == candidate_id)
            )
            evidence_count = await session.scalar(
                select(func.count())
                .select_from(CandidateFieldEvidence)
                .where(CandidateFieldEvidence.candidate_id == candidate_id)
            )
        await engine.dispose()
        return int(fact_count or 0), int(evidence_count or 0)

    def test_register_create_project_import_candidate_and_fetch_dashboard(self) -> None:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": "db-flow-password"},
        )
        self.assertEqual(register_response.status_code, 201, register_response.text)
        token = register_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        project_response = self.client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "DB Flow Project",
                "max_budget": 22000,
                "preferred_districts": ["Wan Chai"],
                "must_have": ["furnished"],
                "deal_breakers": ["shared bathroom"],
            },
        )
        self.assertEqual(project_response.status_code, 201, project_response.text)
        project_id = project_response.json()["id"]

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(return_value=_valid_extraction_payload()),
        ):
            candidate_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/import",
                headers=headers,
                data={
                    "name": "DB Flow Candidate",
                    "raw_listing_text": "Wan Chai flat, rent 18000, deposit 2 months, lease 2 years.",
                    "raw_chat_text": "Agent says management fee may be separate.",
                },
            )
        self.assertEqual(candidate_response.status_code, 201, candidate_response.text)
        candidate_payload = candidate_response.json()
        self.assertEqual(candidate_payload["name"], "DB Flow Candidate")
        candidate_id = candidate_payload["id"]

        candidate_detail_response = self.client.get(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
        )
        self.assertEqual(
            candidate_detail_response.status_code,
            200,
            candidate_detail_response.text,
        )
        candidate_detail = candidate_detail_response.json()
        self.assertEqual(candidate_detail["processing_stage"], "completed")
        self.assertIsNotNone(candidate_detail["candidate_assessment"])
        self.assertEqual(
            asyncio.run(self._field_record_counts(uuid.UUID(candidate_id))),
            (14, 4),
        )

        field_url = f"/api/v1/projects/{project_id}/candidates/{candidate_id}/fields"
        corrected_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "correct", "value": 20000, "note": "Confirmed with landlord"},
        )
        self.assertEqual(corrected_response.status_code, 200, corrected_response.text)
        self.assertEqual(corrected_response.json()["extracted_info"]["monthly_rent"], "20000")
        self.assertEqual(corrected_response.json()["cost_assessment"]["known_monthly_cost"], 20000)

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(return_value=_valid_extraction_payload()),
        ):
            reanalysis_with_override = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/{candidate_id}/reassess",
                headers=headers,
            )

        self.assertEqual(
            reanalysis_with_override.status_code,
            200,
            reanalysis_with_override.text,
        )
        reanalysis_payload = reanalysis_with_override.json()
        self.assertEqual(reanalysis_payload["extracted_info"]["monthly_rent"], "20000")
        self.assertEqual(reanalysis_payload["cost_assessment"]["known_monthly_cost"], 20000)

        dashboard_response = self.client.get(
            f"/api/v1/projects/{project_id}/dashboard",
            headers=headers,
        )
        self.assertEqual(dashboard_response.status_code, 200, dashboard_response.text)
        dashboard_payload = dashboard_response.json()

        self.assertEqual(dashboard_payload["project_id"], project_id)
        self.assertGreaterEqual(dashboard_payload["stats"]["total"], 1)
        self.assertTrue(dashboard_payload["current_advice"])
        self.assertGreaterEqual(len(dashboard_payload["priority_candidates"]), 1)

        original_system_status = candidate_detail["status"]
        original_assessment_status = candidate_detail["candidate_assessment"]["status"]

        shortlist_response = self.client.post(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}/shortlist",
            headers=headers,
        )
        self.assertEqual(shortlist_response.status_code, 200, shortlist_response.text)
        shortlisted = shortlist_response.json()
        self.assertEqual(shortlisted["user_decision"], "shortlisted")
        self.assertEqual(shortlisted["status"], original_system_status)
        self.assertEqual(
            shortlisted["candidate_assessment"]["status"],
            original_assessment_status,
        )

        shortlisted_dashboard = self.client.get(
            f"/api/v1/projects/{project_id}/dashboard",
            headers=headers,
        ).json()
        self.assertEqual(shortlisted_dashboard["stats"]["shortlisted"], 1)
        self.assertEqual(shortlisted_dashboard["stats"]["recommended_reject"], 0)

        reject_response = self.client.post(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}/reject",
            headers=headers,
        )
        self.assertEqual(reject_response.status_code, 200, reject_response.text)
        rejected = reject_response.json()
        self.assertEqual(rejected["user_decision"], "rejected")
        self.assertEqual(rejected["status"], original_system_status)
        self.assertEqual(rejected["candidate_assessment"]["status"], original_assessment_status)

        rejected_dashboard = self.client.get(
            f"/api/v1/projects/{project_id}/dashboard",
            headers=headers,
        ).json()
        self.assertEqual(rejected_dashboard["stats"]["shortlisted"], 0)
        self.assertEqual(rejected_dashboard["stats"]["rejected"], 1)
        self.assertEqual(rejected_dashboard["stats"]["recommended_reject"], 0)

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(side_effect=TimeoutError("provider timed out")),
        ):
            reassess_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/{candidate_id}/reassess",
                headers=headers,
            )

        self.assertEqual(reassess_response.status_code, 200, reassess_response.text)
        reassessed = reassess_response.json()
        self.assertEqual(reassessed["processing_stage"], "failed")
        self.assertEqual(reassessed["processing_error_code"], "llm_unavailable")
        self.assertIsNone(reassessed["extracted_info"])
        self.assertIsNone(reassessed["cost_assessment"])
        self.assertIsNone(reassessed["clause_assessment"])
        self.assertIsNone(reassessed["candidate_assessment"])

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(return_value=_valid_extraction_payload()),
        ):
            retry_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/{candidate_id}/reassess",
                headers=headers,
            )

        self.assertEqual(retry_response.status_code, 200, retry_response.text)
        retried = retry_response.json()
        self.assertEqual(retried["processing_stage"], "completed")
        self.assertIsNone(retried["processing_error_code"])
        self.assertIsNotNone(retried["candidate_assessment"])
        self.assertEqual(retried["user_decision"], "rejected")
        self.assertEqual(retried["status"], retried["candidate_assessment"]["status"])

    def test_missing_llm_configuration_persists_safe_failed_state(self) -> None:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": "db-flow-password"},
        )
        self.assertEqual(register_response.status_code, 201, register_response.text)
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        project_response = self.client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Failed analysis project", "max_budget": 22000},
        )
        self.assertEqual(project_response.status_code, 201, project_response.text)
        project_id = project_response.json()["id"]

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(side_effect=ValueError("GROQ_API_KEY is required for Groq provider")),
        ):
            candidate_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/import",
                headers=headers,
                data={
                    "name": "Saved source",
                    "raw_listing_text": "Wan Chai flat, rent 18000.",
                },
            )
        self.assertEqual(candidate_response.status_code, 201, candidate_response.text)
        candidate_id = candidate_response.json()["id"]

        detail_response = self.client.get(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["processing_stage"], "failed")
        self.assertEqual(detail["processing_error_code"], "llm_not_configured")
        self.assertIn("source information is saved", detail["processing_error"])
        self.assertNotIn("GROQ_API_KEY", detail["processing_error"])
        self.assertIsNone(detail["candidate_assessment"])

    def test_valid_but_unknown_information_never_becomes_reject(self) -> None:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": "db-flow-password"},
        )
        self.assertEqual(register_response.status_code, 201, register_response.text)
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        project_response = self.client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Unknown information project",
                "max_budget": 22000,
                "must_have": ["furnished"],
                "deal_breakers": ["shared bathroom"],
            },
        )
        self.assertEqual(project_response.status_code, 201, project_response.text)
        project_id = project_response.json()["id"]

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(return_value=_all_unknown_extraction_payload()),
        ):
            candidate_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/import",
                headers=headers,
                data={
                    "name": "Vague listing",
                    "raw_listing_text": "Please ask the agent for all rental details.",
                },
            )

        self.assertEqual(candidate_response.status_code, 201, candidate_response.text)
        candidate_id = candidate_response.json()["id"]
        detail_response = self.client.get(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["processing_stage"], "completed")
        self.assertEqual(detail["cost_assessment"]["cost_risk_flag"], "incomplete")
        self.assertEqual(detail["candidate_assessment"]["potential_value_level"], "unknown")
        self.assertEqual(detail["candidate_assessment"]["decision_risk_level"], "unknown")
        self.assertEqual(detail["candidate_assessment"]["top_level_recommendation"], "not_ready")
        self.assertEqual(detail["candidate_assessment"]["next_best_action"], "verify_cost")
        self.assertNotEqual(detail["status"], "recommended_reject")

    def test_field_actions_are_typed_audited_and_transactional(self) -> None:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": "db-flow-password"},
        )
        self.assertEqual(register_response.status_code, 201, register_response.text)
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
        me_response = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_response.status_code, 200, me_response.text)
        user_id = uuid.UUID(me_response.json()["id"])

        project_response = self.client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Field action project", "max_budget": 22000},
        )
        self.assertEqual(project_response.status_code, 201, project_response.text)
        project_id = project_response.json()["id"]

        with patch(
            "app.services.extraction_service.chat_completion_json",
            AsyncMock(return_value=_valid_extraction_payload()),
        ):
            candidate_response = self.client.post(
                f"/api/v1/projects/{project_id}/candidates/import",
                headers=headers,
                data={
                    "name": "Field action candidate",
                    "raw_listing_text": "Wan Chai flat, rent 18000, deposit 2 months, lease 2 years.",
                },
            )
        self.assertEqual(candidate_response.status_code, 201, candidate_response.text)
        candidate_id = candidate_response.json()["id"]

        detail = self.client.get(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
        ).json()
        self.assertEqual(len(detail["field_facts"]), 14)
        rent = next(fact for fact in detail["field_facts"] if fact["key"] == "monthly_rent")
        self.assertEqual(rent["state"], "explicit")
        self.assertEqual(rent["value"], 18000)
        self.assertEqual(rent["evidence"][0]["source_label"], "Listing text")

        field_url = f"/api/v1/projects/{project_id}/candidates/{candidate_id}/fields"
        confirmed_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "confirm", "note": "Confirmed by phone"},
        )
        self.assertEqual(confirmed_response.status_code, 200, confirmed_response.text)
        confirmed_rent = next(
            fact
            for fact in confirmed_response.json()["field_facts"]
            if fact["key"] == "monthly_rent"
        )
        self.assertEqual(confirmed_rent["state"], "user_confirmed")
        self.assertEqual(confirmed_rent["value"], 18000)

        corrected_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "correct", "value": 20000},
        )
        self.assertEqual(corrected_response.status_code, 200, corrected_response.text)
        corrected = corrected_response.json()
        corrected_rent = next(
            fact for fact in corrected["field_facts"] if fact["key"] == "monthly_rent"
        )
        self.assertEqual(corrected_rent["state"], "user_corrected")
        self.assertEqual(corrected_rent["value"], 20000)
        self.assertEqual(corrected["extracted_info"]["monthly_rent"], "20000")
        self.assertEqual(corrected["cost_assessment"]["known_monthly_cost"], 20000)

        invalid_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "correct", "value": "twenty thousand"},
        )
        self.assertEqual(invalid_response.status_code, 422, invalid_response.text)

        with patch(
            "app.api.v1.candidates.pipeline_service.reassess_after_field_change",
            AsyncMock(side_effect=RuntimeError("forced local reassessment failure")),
        ):
            with self.assertRaises(RuntimeError):
                self.client.patch(
                    f"{field_url}/monthly_rent",
                    headers=headers,
                    json={"action": "correct", "value": 21000},
                )

        after_rollback = self.client.get(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
        ).json()
        rollback_rent = next(
            fact for fact in after_rollback["field_facts"] if fact["key"] == "monthly_rent"
        )
        self.assertEqual(rollback_rent["value"], 20000)

        unknown_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "mark_unknown"},
        )
        self.assertEqual(unknown_response.status_code, 200, unknown_response.text)
        unknown = unknown_response.json()
        unknown_rent = next(
            fact for fact in unknown["field_facts"] if fact["key"] == "monthly_rent"
        )
        self.assertEqual(unknown_rent["state"], "user_marked_unknown")
        self.assertIsNone(unknown["extracted_info"]["monthly_rent"])

        reverted_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=headers,
            json={"action": "revert"},
        )
        self.assertEqual(reverted_response.status_code, 200, reverted_response.text)
        reverted = reverted_response.json()
        reverted_rent = next(
            fact for fact in reverted["field_facts"] if fact["key"] == "monthly_rent"
        )
        self.assertEqual(reverted_rent["state"], "explicit")
        self.assertEqual(reverted_rent["value"], 18000)

        unsupported_response = self.client.patch(
            f"{field_url}/furnished",
            headers=headers,
            json={"action": "correct", "value": "furnished"},
        )
        self.assertEqual(unsupported_response.status_code, 422)

        other_register = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.other_email, "password": "db-flow-password"},
        )
        self.assertEqual(other_register.status_code, 201, other_register.text)
        other_headers = {
            "Authorization": f"Bearer {other_register.json()['access_token']}"
        }
        cross_user_response = self.client.patch(
            f"{field_url}/monthly_rent",
            headers=other_headers,
            json={"action": "correct", "value": 1},
        )
        self.assertEqual(cross_user_response.status_code, 404)

        asyncio.run(self._insert_commute_cache(uuid.UUID(candidate_id)))
        location_response = self.client.patch(
            f"{field_url}/district",
            headers=headers,
            json={"action": "correct", "value": "Causeway Bay"},
        )
        self.assertEqual(location_response.status_code, 200, location_response.text)
        self.assertIsNone(location_response.json()["commute_evidence"])

        asyncio.run(self._insert_commute_cache(uuid.UUID(candidate_id)))
        legacy_location_response = self.client.put(
            f"/api/v1/projects/{project_id}/candidates/{candidate_id}",
            headers=headers,
            json={"building_name": "Harbour View Building"},
        )
        self.assertEqual(
            legacy_location_response.status_code,
            200,
            legacy_location_response.text,
        )
        legacy_building = next(
            fact
            for fact in legacy_location_response.json()["field_facts"]
            if fact["key"] == "building_name"
        )
        self.assertEqual(legacy_building["state"], "user_corrected")
        self.assertEqual(legacy_building["value"], "Harbour View Building")
        self.assertIsNone(legacy_location_response.json()["commute_evidence"])

        self.assertEqual(
            asyncio.run(
                self._field_action_counts(
                    candidate_id=uuid.UUID(candidate_id),
                    actor_user_id=user_id,
                )
            ),
            (6, 0),
        )

    async def _insert_commute_cache(self, candidate_id: uuid.UUID) -> None:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(
                CandidateCommuteEvidence(
                    candidate_id=candidate_id,
                    config_signature="test-signature",
                    status="ready",
                    estimated_minutes=20,
                )
            )
            await session.commit()
        await engine.dispose()

    async def _field_action_counts(
        self,
        *,
        candidate_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> tuple[int, int]:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            revision_count = await session.scalar(
                select(func.count())
                .select_from(CandidateFieldRevision)
                .where(
                    CandidateFieldRevision.candidate_id == candidate_id,
                    CandidateFieldRevision.actor_user_id == actor_user_id,
                )
            )
            commute_count = await session.scalar(
                select(func.count())
                .select_from(CandidateCommuteEvidence)
                .where(CandidateCommuteEvidence.candidate_id == candidate_id)
            )
        await engine.dispose()
        return int(revision_count or 0), int(commute_count or 0)

    def test_candidate_field_schema_enforces_contract_and_cascades(self) -> None:
        asyncio.run(self._exercise_candidate_field_schema())

    async def _exercise_candidate_field_schema(self) -> None:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        candidate_id: uuid.UUID

        async with session_factory() as session:
            user = User(email=self.email, password_hash="not-used-in-schema-test")
            project = SearchProject(user=user, title="Field schema project")
            candidate = CandidateListing(
                project=project,
                name="Field schema candidate",
                raw_listing_text="Rent HKD 18,000",
                combined_text="Rent HKD 18,000",
            )
            fact = CandidateFieldFact(
                candidate=candidate,
                field_key="monthly_rent",
                system_value=18_000,
                system_state="explicit",
                system_confidence="high",
            )
            fact.evidence.append(
                CandidateFieldEvidence(
                    candidate_id=candidate.id,
                    field_key="monthly_rent",
                    source_type="listing",
                    quote="Rent HKD 18,000",
                    claim_value=18_000,
                    claim_kind="explicit",
                    confidence="high",
                )
            )
            fact.revisions.append(
                CandidateFieldRevision(
                    candidate_id=candidate.id,
                    field_key="monthly_rent",
                    actor_user=user,
                    action="confirm",
                    previous_value=None,
                    new_value=18_000,
                )
            )
            session.add(user)
            await session.commit()
            candidate_id = candidate.id

            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldFact)
                    .where(CandidateFieldFact.candidate_id == candidate_id)
                ),
                1,
            )
            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldEvidence)
                    .where(CandidateFieldEvidence.candidate_id == candidate_id)
                ),
                1,
            )
            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldRevision)
                    .where(CandidateFieldRevision.candidate_id == candidate_id)
                ),
                1,
            )

            session.add(
                CandidateFieldFact(
                    candidate_id=candidate_id,
                    field_key="deposit",
                    system_value="2 months",
                    system_state="unknown",
                    system_confidence="low",
                )
            )
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()

            await session.execute(
                delete(CandidateListing).where(CandidateListing.id == candidate_id)
            )
            await session.commit()
            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldFact)
                    .where(CandidateFieldFact.candidate_id == candidate_id)
                ),
                0,
            )
            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldEvidence)
                    .where(CandidateFieldEvidence.candidate_id == candidate_id)
                ),
                0,
            )
            self.assertEqual(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateFieldRevision)
                    .where(CandidateFieldRevision.candidate_id == candidate_id)
                ),
                0,
            )

        await engine.dispose()

    def test_reanalysis_replaces_system_evidence_but_preserves_user_override(self) -> None:
        asyncio.run(self._exercise_field_evidence_replacement())

    async def _exercise_field_evidence_replacement(self) -> None:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(email=self.email, password_hash="not-used-in-evidence-test")
            project = SearchProject(user=user, title="Evidence replacement project")
            candidate = CandidateListing(
                project=project,
                name="Evidence replacement candidate",
                raw_listing_text="Updated rent HKD 19,000",
                combined_text="Updated rent HKD 19,000",
            )
            fact = CandidateFieldFact(
                candidate=candidate,
                field_key="monthly_rent",
                system_value=18_000,
                system_state="explicit",
                system_confidence="high",
                user_action="corrected",
                user_value=17_500,
                user_note="Landlord confirmed this directly",
            )
            fact.evidence.append(
                CandidateFieldEvidence(
                    candidate_id=candidate.id,
                    field_key="monthly_rent",
                    source_type="listing",
                    quote="Old rent HKD 18,000",
                    claim_value=18_000,
                    claim_kind="explicit",
                    confidence="high",
                )
            )
            fact.revisions.append(
                CandidateFieldRevision(
                    candidate_id=candidate.id,
                    field_key="monthly_rent",
                    actor_user=user,
                    action="correct",
                    previous_value=18_000,
                    new_value=17_500,
                    note="Landlord confirmed this directly",
                )
            )
            session.add(user)
            await session.commit()

            merged_facts = merge_field_claims(
                (
                    VerifiedFieldClaim(
                        field_key="monthly_rent",
                        value=19_000,
                        source_type="listing",
                        source_asset_id=None,
                        quote="Updated rent HKD 19,000",
                        claim_kind="explicit",
                        confidence="high",
                    ),
                )
            )
            await CandidateFieldEvidenceService().replace_system_results(
                session,
                candidate_id=candidate.id,
                facts=merged_facts,
            )
            await session.commit()

            result = await session.execute(
                select(CandidateFieldFact).where(
                    CandidateFieldFact.candidate_id == candidate.id
                )
            )
            stored_facts = {stored.field_key: stored for stored in result.scalars().all()}
            self.assertEqual(len(stored_facts), 14)
            self.assertEqual(stored_facts["monthly_rent"].system_value, 19_000)
            self.assertEqual(stored_facts["monthly_rent"].user_action, "corrected")
            self.assertEqual(stored_facts["monthly_rent"].user_value, 17_500)
            self.assertEqual(
                stored_facts["monthly_rent"].user_note,
                "Landlord confirmed this directly",
            )
            self.assertEqual(stored_facts["deposit"].system_state, "unknown")

            evidence = (
                await session.execute(
                    select(CandidateFieldEvidence).where(
                        CandidateFieldEvidence.candidate_id == candidate.id
                    )
                )
            ).scalars().all()
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].quote, "Updated rent HKD 19,000")

            revisions = (
                await session.execute(
                    select(CandidateFieldRevision).where(
                        CandidateFieldRevision.candidate_id == candidate.id
                    )
                )
            ).scalars().all()
            self.assertEqual(len(revisions), 1)
            self.assertEqual(revisions[0].action, "correct")
            self.assertEqual(revisions[0].new_value, 17_500)
            self.assertEqual(
                revisions[0].note,
                "Landlord confirmed this directly",
            )

        await engine.dispose()

    def test_zz_candidate_field_migration_round_trip(self) -> None:
        expected_tables = {
            "candidate_field_facts",
            "candidate_field_evidence",
            "candidate_field_revisions",
        }
        self.assertEqual(asyncio.run(self._candidate_field_table_names()), expected_tables)

        try:
            command.downgrade(self.alembic_cfg, "20260812_0014")
            self.assertEqual(asyncio.run(self._candidate_field_table_names()), set())
        finally:
            command.upgrade(self.alembic_cfg, "head")

        self.assertEqual(asyncio.run(self._candidate_field_table_names()), expected_tables)

    async def _candidate_field_table_names(self) -> set[str]:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name LIKE 'candidate_field_%'"
                    )
                )
                return set(result.scalars())
        finally:
            await engine.dispose()
