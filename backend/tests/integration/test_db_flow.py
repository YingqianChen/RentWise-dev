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
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.db.models import User
from app.main import app


def _valid_extraction_payload() -> dict[str, object]:
    return {
        "address_text": "unknown",
        "building_name": "unknown",
        "nearest_station": "unknown",
        "district": "Wan Chai",
        "location_confidence": "low",
        "monthly_rent": "18000",
        "management_fee_amount": "unknown",
        "management_fee_included": "unknown",
        "rates_amount": "unknown",
        "rates_included": "unknown",
        "deposit": "2 months",
        "agent_fee": "unknown",
        "lease_term": "2 years",
        "move_in_date": "unknown",
        "repair_responsibility": "unknown",
        "furnished": "unknown",
        "size_sqft": "unknown",
        "bedrooms": "unknown",
        "suspected_sdu": "unknown",
        "sdu_detection_reason": "unknown",
        "decision_signals": [],
        "raw_facts": [],
    }


def _all_unknown_extraction_payload() -> dict[str, object]:
    payload = _valid_extraction_payload()
    for key in (
        "address_text",
        "building_name",
        "nearest_station",
        "district",
        "location_confidence",
        "monthly_rent",
        "management_fee_amount",
        "rates_amount",
        "deposit",
        "agent_fee",
        "lease_term",
        "move_in_date",
        "repair_responsibility",
        "furnished",
        "size_sqft",
        "bedrooms",
        "suspected_sdu",
        "sdu_detection_reason",
    ):
        payload[key] = "unknown"
    payload["management_fee_included"] = "unknown"
    payload["rates_included"] = "unknown"
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

        alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self) -> None:
        self.email = f"db-flow-{uuid.uuid4().hex[:12]}@example.com"

    def tearDown(self) -> None:
        asyncio.run(self._cleanup_user())

    async def _cleanup_user(self) -> None:
        engine = create_async_engine(settings.DATABASE_URL, future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(delete(User).where(User.email == self.email))
            await session.commit()
        await engine.dispose()

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
