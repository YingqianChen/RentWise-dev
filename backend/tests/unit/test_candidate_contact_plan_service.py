from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.candidate_contact_plan_service import CandidateContactPlanService
from tests.helpers import build_candidate, build_project, build_user


class CandidateContactPlanServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = CandidateContactPlanService()
        self.project = build_project(build_user())
        self.candidate = build_candidate(self.project)

    def test_fallback_never_reasks_explicit_core_fields(self):
        fallback = self.service._fallback(candidate=self.candidate)
        text = " ".join(fallback.questions).lower()

        self.assertNotIn("exact monthly rent", text)
        self.assertNotIn("required deposit", text)
        self.assertNotIn("lease term", text)
        self.assertNotIn("move-in date", text)
        self.assertNotIn("building name or exact location", text)

    def test_inferred_field_becomes_a_question_but_does_not_enter_known_context(self):
        lease = next(fact for fact in self.candidate.field_facts if fact.field_key == "lease_term")
        lease.system_state = "inferred"
        lease.system_value = "2 years"
        self.candidate.extracted_info.lease_term = None
        self.candidate.candidate_assessment.next_best_action = "verify_clause"

        fallback = self.service._fallback(candidate=self.candidate)

        self.assertTrue(any("lease term" in question.lower() for question in fallback.questions))
        self.assertIn("Lease term: unknown", self.service._candidate_context(self.candidate))

    def test_generated_questions_are_restricted_to_preapproved_unknowns(self):
        fallback = self.service._fallback(candidate=self.candidate)

        questions = self.service._clean_questions(
            [
                fallback.questions[0],
                "Could you reconfirm the monthly rent of HKD 18,000?",
            ],
            fallback.questions,
        )

        self.assertEqual(questions, fallback.questions)

    def test_fallback_uses_project_preferences_as_questions(self):
        fallback = self.service._fallback(project=self.project, candidate=self.candidate)

        self.assertTrue(
            any(
                "must-have conditions" in question or "conditions apply" in question
                for question in fallback.questions
            )
        )
        preference_questions = self.service._preference_questions(self.project)
        self.assertEqual(len(preference_questions), 2)

    def test_chinese_and_english_drafts_cover_the_same_questions(self):
        fallback = self.service._fallback(project=self.project, candidate=self.candidate)

        self.assertEqual(len(fallback.questions), len(fallback.questions_zh))
        self.assertIn("Hi, I am interested", fallback.message_draft)
        self.assertIn("你好", fallback.message_draft_zh)

    def test_question_deduplication_normalizes_spacing_case_and_punctuation(self):
        questions = self.service._dedupe(
            [
                "  Could you confirm the exact monthly rent? ",
                "could you confirm the exact monthly rent???",
            ]
        )

        self.assertEqual(questions, ["  Could you confirm the exact monthly rent? "])
