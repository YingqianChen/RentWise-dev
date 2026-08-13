"""Generate a lightweight outreach plan for the next landlord/agent message."""

from __future__ import annotations

import logging

from ..db.models import CandidateListing, SearchProject
from ..integrations.llm.prompts import CONTACT_PLAN_PROMPT
from ..integrations.llm.utils import chat_completion_json
from ..schemas.candidate import CandidateContactPlanResponse
from .candidate_field_read_service import candidate_field_state, field_needs_confirmation

logger = logging.getLogger(__name__)


class CandidateContactPlanService:
    """Build a concise outreach plan without duplicating the page assessment."""

    async def build(
        self,
        *,
        project: SearchProject,
        candidate: CandidateListing,
    ) -> CandidateContactPlanResponse:
        fallback = self._fallback(candidate=candidate)

        prompt = CONTACT_PLAN_PROMPT.format(
            project_context=self._project_context(project),
            candidate_context=self._candidate_context(candidate),
            decision_context=self._decision_context(candidate),
            blockers_context=self._blockers_context(candidate, fallback.questions),
        )

        try:
            data = await chat_completion_json(
                prompt=prompt,
                temperature=0.2,
                max_tokens=300,
            )
            questions = self._clean_questions(data.get("questions"), fallback.questions)
            return CandidateContactPlanResponse(
                contact_goal=self._clean_line(data.get("contact_goal"), fallback.contact_goal),
                questions=questions,
                message_draft=self._build_message(candidate, questions),
            )
        except Exception as exc:
            logger.error("Candidate contact plan generation failed: %s", exc)
            return fallback

    def _fallback(self, *, candidate: CandidateListing) -> CandidateContactPlanResponse:
        assessment = candidate.candidate_assessment
        next_action = assessment.next_best_action if assessment is not None else "keep_warm"
        deduped_questions = self._dedupe(self._unresolved_questions(candidate))[:3]
        supplemental_questions = [
            "Could you confirm whether the property is offered as a whole unit and whether the bathroom is private?",
            "Could you let me know what furniture or appliances will remain in the property?",
            "Could you share the available viewing times?",
        ]
        for question in supplemental_questions:
            if len(deduped_questions) >= 2:
                break
            deduped_questions.append(question)

        goal_map = {
            "verify_cost": "Clarify the real monthly and upfront cost before deciding whether this listing stays viable.",
            "verify_clause": "Resolve the lease and responsibility questions that could still change the decision.",
            "schedule_viewing": "Confirm the last practical details and move this option toward a viewing.",
            "reject": "Check whether any missing detail could realistically reverse the current weak fit.",
            "keep_warm": "Tighten the key unknowns so you can judge whether this listing deserves more attention.",
        }
        contact_goal = goal_map.get(next_action, goal_map["keep_warm"])

        return CandidateContactPlanResponse(
            contact_goal=contact_goal,
            questions=deduped_questions,
            message_draft=self._build_message(candidate, deduped_questions),
        )

    def _unresolved_questions(self, candidate: CandidateListing) -> list[str]:
        cost_questions: list[str] = []
        clause_questions: list[str] = []
        location_questions: list[str] = []
        if field_needs_confirmation(candidate, "monthly_rent"):
            cost_questions.append("Could you confirm the exact monthly rent?")

        if field_needs_confirmation(candidate, "management_fee_included"):
            cost_questions.append(
                "Could you confirm whether the management fee is included and, if not, how much it is per month?"
            )
        elif (
            candidate.extracted_info is not None
            and candidate.extracted_info.management_fee_included is False
            and field_needs_confirmation(candidate, "management_fee_amount")
        ):
            cost_questions.append("Could you confirm the monthly management fee amount?")

        if field_needs_confirmation(candidate, "rates_included"):
            cost_questions.append(
                "Could you confirm whether government rates are included and what the amount is if they are separate?"
            )
        elif (
            candidate.extracted_info is not None
            and candidate.extracted_info.rates_included is False
            and field_needs_confirmation(candidate, "rates_amount")
        ):
            cost_questions.append("Could you confirm the amount of the separate government rates?")

        cost_field_questions = (
            ("deposit", "Could you confirm the required deposit?"),
            ("agent_fee", "Could you confirm whether an agent fee applies and how much it is?"),
        )
        for field_key, question in cost_field_questions:
            if field_needs_confirmation(candidate, field_key):
                cost_questions.append(question)

        clause_field_questions = (
            ("lease_term", "Could you confirm the lease term, break clause, and early termination conditions?"),
            ("move_in_date", "Could you confirm the earliest realistic move-in date?"),
            (
                "repair_responsibility",
                "Could you clarify which repairs are covered by the landlord and whether that is stated in the agreement?",
            ),
        )
        for field_key, question in clause_field_questions:
            if field_needs_confirmation(candidate, field_key):
                clause_questions.append(question)

        if all(
            field_needs_confirmation(candidate, field_key)
            for field_key in ("district", "address_text", "building_name", "nearest_station")
        ):
            location_questions.append("Could you confirm the building name or exact location?")

        assessment = candidate.candidate_assessment
        if assessment is not None and assessment.next_best_action == "verify_clause":
            return clause_questions + cost_questions + location_questions
        return cost_questions + clause_questions + location_questions

    def _project_context(self, project: SearchProject) -> str:
        preferred = ", ".join(project.preferred_districts) if project.preferred_districts else "No preferred districts stated"
        must_have = ", ".join(project.must_have) if project.must_have else "No must-have list stated"
        deal_breakers = ", ".join(project.deal_breakers) if project.deal_breakers else "No deal breakers stated"
        return (
            f"Budget cap: {project.max_budget or 'unknown'}\n"
            f"Preferred districts: {preferred}\n"
            f"Must have: {must_have}\n"
            f"Deal breakers: {deal_breakers}\n"
            f"Move-in target: {project.move_in_target or 'unknown'}"
        )

    def _candidate_context(self, candidate: CandidateListing) -> str:
        extracted = candidate.extracted_info
        if extracted is None:
            return f"Candidate name: {candidate.name}\nNo structured extraction is available yet."
        return (
            f"Candidate name: {candidate.name}\n"
            f"District: {extracted.district or 'unknown'}\n"
            f"Monthly rent: {extracted.monthly_rent or 'unknown'}\n"
            f"Lease term: {extracted.lease_term or 'unknown'}\n"
            f"Move-in date: {extracted.move_in_date or 'unknown'}\n"
            f"Repair responsibility note: {extracted.repair_responsibility or 'unknown'}"
        )

    def _decision_context(self, candidate: CandidateListing) -> str:
        assessment = candidate.candidate_assessment
        if assessment is None:
            return "No overall candidate assessment is available yet."
        return (
            f"Top recommendation: {assessment.top_level_recommendation}\n"
            f"Next best action: {assessment.next_best_action}\n"
            f"Recommendation confidence: {assessment.recommendation_confidence}\n"
            f"Summary: {assessment.summary}"
        )

    def _blockers_context(self, candidate: CandidateListing, allowed_questions: list[str]) -> str:
        lines: list[str] = []
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment
        if cost is not None:
            if cost.monthly_cost_missing_items:
                lines.append("Missing cost fields: " + ", ".join(cost.monthly_cost_missing_items))
            lines.append(f"Cost risk: {cost.cost_risk_flag}")
        if clause is not None:
            lines.append(f"Repair responsibility level: {clause.repair_responsibility_level}")
            lines.append(f"Lease term level: {clause.lease_term_level}")
            lines.append(f"Move-in timing level: {clause.move_in_date_level}")
            lines.append(f"Clause risk: {clause.clause_risk_flag}")
        unresolved_states = [
            f"{fact.field_key}: {candidate_field_state(candidate, fact.field_key)}"
            for fact in candidate.field_facts
            if field_needs_confirmation(candidate, fact.field_key)
        ]
        if unresolved_states:
            lines.append("Unresolved field states: " + ", ".join(unresolved_states))
        lines.append("Allowed questions (copy exactly; do not add or paraphrase):")
        lines.extend(f"- {question}" for question in allowed_questions)
        return "\n".join(lines) if lines else "No structured blockers are available."

    def _clean_line(self, value: object, fallback: str) -> str:
        if not isinstance(value, str):
            return fallback
        cleaned = " ".join(value.split())
        return cleaned if cleaned else fallback

    def _clean_questions(self, value: object, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        allowed = {" ".join(question.split()).lower(): question for question in fallback}
        cleaned: list[str] = []
        for item in value:
            if isinstance(item, str):
                normalized = " ".join(item.split())
                allowed_question = allowed.get(normalized.lower())
                if allowed_question:
                    cleaned.append(allowed_question)
        deduped = self._dedupe(cleaned)
        return deduped[:3] if len(deduped) >= 2 else fallback

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _join_questions_for_message(self, questions: list[str]) -> str:
        if len(questions) == 1:
            return questions[0]
        if len(questions) == 2:
            return f"{questions[0]} Also, {questions[1].lower()}"
        return f"{questions[0]} Also, {questions[1].lower()} Finally, {questions[2].lower()}"

    def _build_message(self, candidate: CandidateListing, questions: list[str]) -> str:
        return (
            f"Hi, I am interested in {candidate.name} and would like to clarify a few practical points before deciding my next step. "
            f"Could you please help with the following: {self._join_questions_for_message(questions)} "
            "Thanks in advance."
        )
