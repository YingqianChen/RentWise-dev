from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import CandidateFieldFact
from app.services.candidate_field_projection_service import CandidateFieldProjectionService
from app.services.candidate_field_registry import CANDIDATE_FIELD_KEYS
from app.services.cost_assessment_service import CostAssessmentService
from tests.helpers import build_candidate, build_project, build_user


class CandidateDecisionFieldContractTests(TestCase):
    def test_only_three_decision_usable_states_can_trigger_over_budget(self):
        cases = (
            ("explicit", "explicit", None, None, True),
            ("inferred", "inferred", None, None, False),
            ("conflicted", "conflicted", None, None, False),
            ("unknown", "unknown", None, None, False),
            ("user_confirmed", "inferred", "confirmed", 30000, True),
            ("user_corrected", "explicit", "corrected", 30000, True),
            ("user_marked_unknown", "explicit", "marked_unknown", None, False),
        )

        for label, system_state, user_action, user_value, should_reject in cases:
            with self.subTest(state=label):
                candidate = build_candidate(build_project(build_user()))
                facts = [
                    CandidateFieldFact(
                        candidate_id=candidate.id,
                        field_key=field_key,
                        system_value=None,
                        system_state="unknown",
                        system_confidence="low",
                    )
                    for field_key in CANDIDATE_FIELD_KEYS
                ]
                by_key = {fact.field_key: fact for fact in facts}
                rent = by_key["monthly_rent"]
                rent.system_state = system_state
                rent.system_value = 30000 if system_state in {"explicit", "inferred"} else None
                rent.user_action = user_action
                rent.user_value = user_value
                for field_key in ("management_fee_included", "rates_included"):
                    by_key[field_key].system_state = "explicit"
                    by_key[field_key].system_value = True
                    by_key[field_key].system_confidence = "high"

                CandidateFieldProjectionService().project(
                    extracted_info=candidate.extracted_info,
                    facts=facts,
                )
                cost = CostAssessmentService().assess(
                    candidate.extracted_info,
                    max_budget=22000,
                )

                self.assertEqual(cost.cost_risk_flag == "over_budget", should_reject)
