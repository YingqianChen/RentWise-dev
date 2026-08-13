"""Candidate assessment service for overall candidate evaluation."""

from __future__ import annotations

from typing import List, Optional

from ..db.models import CandidateAssessment, CandidateExtractedInfo, ClauseAssessment, CostAssessment


class CandidateAssessmentService:
    """Combine extracted, cost, and clause data into an actionable candidate assessment."""

    def assess(
        self,
        extracted_info: CandidateExtractedInfo,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        preferred_districts: Optional[List[str]] = None,
    ) -> CandidateAssessment:
        preferred_districts = preferred_districts or []

        hard_conflict = self._has_hard_conflict(cost_assessment)
        potential_value = self._assess_potential_value(
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            preferred_districts=preferred_districts,
            hard_conflict=hard_conflict,
        )
        completeness = self._assess_completeness(
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
        )
        critical_uncertainty = self._assess_critical_uncertainty(
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
        )
        decision_risk = self._assess_decision_risk(
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            hard_conflict=hard_conflict,
        )
        information_gain = self._assess_information_gain(
            completeness=completeness,
            critical_uncertainty=critical_uncertainty,
            potential_value=potential_value,
        )
        recommendation_confidence = self._assess_recommendation_confidence(
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            completeness=completeness,
            critical_uncertainty=critical_uncertainty,
            hard_conflict=hard_conflict,
        )
        next_action = self._determine_next_action(
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            decision_risk=decision_risk,
            recommendation_confidence=recommendation_confidence,
            potential_value=potential_value,
            hard_conflict=hard_conflict,
        )
        status = self._determine_status(
            next_action=next_action,
            decision_risk=decision_risk,
            critical_uncertainty=critical_uncertainty,
        )
        labels = self._generate_labels(
            extracted_info=extracted_info,
            cost_assessment=cost_assessment,
            clause_assessment=clause_assessment,
            hard_conflict=hard_conflict,
        )
        summary = self._generate_summary(
            potential_value=potential_value,
            completeness=completeness,
            next_action=next_action,
            labels=labels,
            hard_conflict=hard_conflict,
        )

        return CandidateAssessment(
            candidate_id=extracted_info.candidate_id,
            potential_value_level=potential_value,
            completeness_level=completeness,
            critical_uncertainty_level=critical_uncertainty,
            decision_risk_level=decision_risk,
            information_gain_level=information_gain,
            recommendation_confidence=recommendation_confidence,
            next_best_action=next_action,
            status=status,
            labels=labels,
            summary=summary,
        )

    def _has_hard_conflict(self, cost_assessment: CostAssessment) -> bool:
        return cost_assessment.cost_risk_flag == "over_budget"

    def _assess_potential_value(
        self,
        extracted_info: CandidateExtractedInfo,
        cost_assessment: CostAssessment,
        preferred_districts: List[str],
        hard_conflict: bool,
    ) -> str:
        if hard_conflict:
            return "low"

        score = 0

        if cost_assessment.cost_risk_flag == "none" and cost_assessment.known_monthly_cost is not None:
            score += 1

        district = extracted_info.district
        normalized_preferred = {item.strip().lower() for item in preferred_districts}
        if not self._is_unknown(district) and district.strip().lower() in normalized_preferred:
            score += 1

        if score >= 2:
            return "high"
        if score >= 1:
            return "medium"
        return "unknown"

    def _assess_completeness(
        self,
        extracted_info: CandidateExtractedInfo,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
    ) -> str:
        missing_count = 0
        if self._is_unknown(extracted_info.monthly_rent):
            missing_count += 2
        if self._is_unknown(extracted_info.deposit):
            missing_count += 1
        if self._is_unknown(extracted_info.lease_term):
            missing_count += 1
        if self._is_unknown(extracted_info.repair_responsibility):
            missing_count += 1
        if cost_assessment.monthly_cost_confidence == "low":
            missing_count += 1
        if clause_assessment.clause_confidence == "low":
            missing_count += 1

        if missing_count <= 1:
            return "high"
        if missing_count <= 3:
            return "medium"
        return "low"

    def _assess_critical_uncertainty(
        self,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
    ) -> str:
        if cost_assessment.known_monthly_cost is None or cost_assessment.monthly_cost_confidence == "low":
            return "high"
        if clause_assessment.clause_risk_flag == "high_risk":
            return "high"
        if clause_assessment.clause_confidence == "low" or clause_assessment.clause_risk_flag == "needs_confirmation":
            return "medium"
        return "low"

    def _assess_decision_risk(
        self,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        hard_conflict: bool,
    ) -> str:
        if hard_conflict:
            return "high"
        if clause_assessment.clause_risk_flag == "high_risk":
            return "high"
        if cost_assessment.cost_risk_flag == "possible_additional_cost":
            return "medium"
        if self._has_explicit_clause_concern(clause_assessment):
            return "medium"
        if cost_assessment.cost_risk_flag in {"incomplete", "over_budget"}:
            return "unknown"
        if self._clause_is_all_unknown(clause_assessment):
            return "unknown"
        return "low"

    def _assess_information_gain(self, completeness: str, critical_uncertainty: str, potential_value: str) -> str:
        if potential_value == "high" and critical_uncertainty in {"high", "medium"}:
            return "high"
        if completeness == "low" or critical_uncertainty == "high":
            return "high"
        if completeness == "medium" or critical_uncertainty == "medium":
            return "medium"
        return "low"

    def _assess_recommendation_confidence(
        self,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        completeness: str,
        critical_uncertainty: str,
        hard_conflict: bool,
    ) -> str:
        if hard_conflict:
            return "low"
        if cost_assessment.known_monthly_cost is None:
            return "low"
        if cost_assessment.monthly_cost_confidence == "low":
            return "low"
        if clause_assessment.clause_confidence == "low":
            return "low"
        if clause_assessment.clause_risk_flag == "high_risk":
            return "low"
        if completeness == "low":
            return "low"
        if completeness == "medium" or critical_uncertainty != "low":
            return "medium"
        return "high"

    def _determine_next_action(
        self,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        decision_risk: str,
        recommendation_confidence: str,
        potential_value: str,
        hard_conflict: bool,
    ) -> str:
        if hard_conflict:
            return "reject"
        if (
            cost_assessment.known_monthly_cost is None
            or cost_assessment.monthly_cost_confidence == "low"
            or cost_assessment.cost_risk_flag in {"incomplete", "possible_additional_cost", "over_budget"}
        ):
            return "verify_cost"
        if clause_assessment.clause_confidence == "low" or clause_assessment.clause_risk_flag in {"needs_confirmation", "high_risk"}:
            return "verify_clause"
        if recommendation_confidence == "high" and potential_value in {"high", "medium"}:
            return "schedule_viewing"
        if potential_value == "high":
            return "keep_warm"
        return "keep_warm"

    def _determine_status(self, next_action: str, decision_risk: str, critical_uncertainty: str) -> str:
        if next_action == "reject":
            return "recommended_reject"
        if next_action in {"verify_cost", "verify_clause"} and decision_risk == "high":
            return "high_risk_pending"
        if next_action in {"verify_cost", "verify_clause"} or critical_uncertainty in {"high", "medium"}:
            return "needs_info"
        return "follow_up"

    def _generate_labels(
        self,
        extracted_info: CandidateExtractedInfo,
        cost_assessment: CostAssessment,
        clause_assessment: ClauseAssessment,
        hard_conflict: bool,
    ) -> List[str]:
        labels: List[str] = []
        if hard_conflict:
            labels.append("Hard conflict")
        if cost_assessment.cost_risk_flag == "over_budget":
            labels.append("Over budget")
        elif cost_assessment.cost_risk_flag == "incomplete":
            labels.append("Cost incomplete")

        if clause_assessment.repair_responsibility_level == "tenant_heavy":
            labels.append("Tenant-heavy repairs")
        if clause_assessment.lease_term_level == "unstable":
            labels.append("Unstable lease")
        if not self._is_unknown(extracted_info.district):
            labels.append(str(extracted_info.district))

        return labels[:5]

    def _generate_summary(
        self,
        potential_value: str,
        completeness: str,
        next_action: str,
        labels: List[str],
        hard_conflict: bool,
    ) -> str:
        if hard_conflict:
            return "This candidate conflicts with your baseline requirements. It is not a good use of more time."

        value_map = {
            "high": "This candidate has strong upside if the remaining blockers are clarified.",
            "medium": "This candidate is still viable, but it needs more confirmation before you can trust it.",
            "low": "This candidate currently looks weak compared with the rest of the pool.",
            "unknown": "There is not enough evidence yet to judge this candidate's potential.",
        }
        action_map = {
            "verify_cost": "Verify the real monthly cost before making any shortlist decision.",
            "verify_clause": "Clarify the key lease terms before deciding whether to keep pushing it.",
            "schedule_viewing": "The information is stable enough to move to a viewing or serious follow-up.",
            "keep_warm": "Keep it in the pool, but it is not the first candidate to push right now.",
            "reject": "The current signal suggests your time is better spent elsewhere.",
        }

        parts = [value_map.get(potential_value, "This candidate still needs review.")]
        if completeness == "low":
            parts.append("Important information is still missing.")
        parts.append(action_map.get(next_action, ""))
        if labels:
            parts.append(f"Key signals: {', '.join(labels)}.")
        return " ".join(part for part in parts if part)

    def _clause_is_all_unknown(self, clause_assessment: ClauseAssessment) -> bool:
        return all(
            level == "unknown"
            for level in (
                clause_assessment.repair_responsibility_level,
                clause_assessment.lease_term_level,
                clause_assessment.move_in_date_level,
            )
        )

    def _has_explicit_clause_concern(self, clause_assessment: ClauseAssessment) -> bool:
        return (
            clause_assessment.repair_responsibility_level in {"unclear", "supported_but_unconfirmed"}
            or clause_assessment.lease_term_level == "rigid"
            or clause_assessment.move_in_date_level in {"mismatch", "uncertain"}
        )

    def _is_unknown(self, value: Optional[str]) -> bool:
        if value is None:
            return True
        return str(value).strip().lower() in {"", "unknown", "n/a", "none"}
