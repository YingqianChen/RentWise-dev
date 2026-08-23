"""Deterministic quality contract for common Hong Kong rental scenarios."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from app.services.candidate_assessment_service import CandidateAssessmentService
from app.services.clause_assessment_service import ClauseAssessmentService
from app.services.cost_assessment_service import CostAssessmentService
from tests.helpers import build_candidate, build_project, build_user


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "assessment_cases.jsonl"
_EXTRACTED_FIELDS = (
    "monthly_rent",
    "management_fee_amount",
    "management_fee_included",
    "rates_amount",
    "rates_included",
    "deposit",
    "agent_fee",
    "lease_term",
    "move_in_date",
    "repair_responsibility",
    "district",
)
_ASSESSMENT_FIELDS = (
    "potential_value_level",
    "completeness_level",
    "critical_uncertainty_level",
    "decision_risk_level",
    "information_gain_level",
    "recommendation_confidence",
    "next_best_action",
    "status",
)


def _load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in _FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _build_project(case: dict):
    project = build_project(build_user())
    project.max_budget = case["project"]["max_budget"]
    project.preferred_districts = case["project"]["preferred_districts"]
    project.move_in_target = date.fromisoformat(case["project"]["move_in_target"])
    return project


def _run_case(case: dict):
    project = _build_project(case)
    candidate = build_candidate(project, candidate_id=UUID(int=0))
    extracted = candidate.extracted_info
    assert extracted is not None
    for field in _EXTRACTED_FIELDS:
        setattr(extracted, field, case["extracted"].get(field))

    cost = CostAssessmentService().assess(extracted, max_budget=project.max_budget)
    clause = ClauseAssessmentService().assess(extracted, move_in_target=project.move_in_target)
    assessment = CandidateAssessmentService().assess(
        extracted_info=extracted,
        cost_assessment=cost,
        clause_assessment=clause,
        preferred_districts=project.preferred_districts,
    )
    return cost, clause, assessment


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_common_hk_rental_scenarios_keep_assessments_consistent(case: dict) -> None:
    cost, clause, assessment = _run_case(case)
    expected = case["expected"]

    assert cost.known_monthly_cost == expected["known_monthly_cost"]
    assert cost.monthly_cost_confidence == expected["monthly_cost_confidence"]
    assert cost.cost_risk_flag == expected["cost_risk_flag"]
    assert clause.clause_risk_flag == expected["clause_risk_flag"]
    for field in _ASSESSMENT_FIELDS:
        assert getattr(assessment, field) == expected[field], (
            f"{case['id']} {field}: "
            f"expected {expected[field]!r}, got {getattr(assessment, field)!r}"
        )
    assert assessment.top_level_recommendation == expected["top_level_recommendation"]

    if assessment.critical_uncertainty_level == "high":
        assert assessment.recommendation_confidence != "high"
        assert assessment.next_best_action != "schedule_viewing"
    if cost.cost_risk_flag in {"incomplete", "possible_additional_cost"}:
        assert assessment.next_best_action == "verify_cost"
    if clause.clause_risk_flag == "high_risk":
        assert assessment.recommendation_confidence != "high"
        assert assessment.next_best_action == "verify_clause"
