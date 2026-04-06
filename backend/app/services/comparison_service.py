"""Comparison service for shortlist decision workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ..db.models import CandidateListing, SearchProject
from ..schemas.comparison import (
    CompareActionTarget,
    CompareCandidateCard,
    CompareDecisionGroups,
    CompareDifference,
    CompareRecommendedActions,
    CompareSummary,
    SuggestedComparePreview,
)
from .dashboard_service import DashboardService
from .benchmark_service import BenchmarkService


@dataclass
class _ComparableCandidate:
    candidate: CandidateListing
    score: float


class ComparisonService:
    """Build grouped shortlist comparisons with explanation-first output."""

    def __init__(self) -> None:
        self.dashboard_service = DashboardService()
        self.benchmark_service = BenchmarkService()

    def compare(self, project: SearchProject, candidates: Iterable[CandidateListing]) -> dict:
        selected = list(candidates)
        best_group: Optional[CompareCandidateCard] = None
        viable_cards: list[CompareCandidateCard] = []
        not_ready_cards: list[CompareCandidateCard] = []
        likely_drop_cards: list[CompareCandidateCard] = []
        comparable: list[_ComparableCandidate] = []

        for candidate in selected:
            group = self._classify_candidate(candidate)
            if group == "likely_drop":
                likely_drop_cards.append(self._build_candidate_card(candidate, group, None))
                continue
            if group == "not_ready":
                not_ready_cards.append(self._build_candidate_card(candidate, group, None))
                continue
            comparable.append(_ComparableCandidate(candidate=candidate, score=self._compare_strength(project, candidate)))

        if comparable:
            comparable.sort(key=lambda item: item.score, reverse=True)
            best = comparable[0].candidate
            best_group = self._build_candidate_card(best, "best_current_option", best)
            viable_cards = [
                self._build_candidate_card(item.candidate, "viable_alternative", best)
                for item in comparable[1:]
            ]

        groups = CompareDecisionGroups(
            best_current_option=best_group,
            viable_alternatives=viable_cards,
            not_ready_for_fair_comparison=not_ready_cards,
            likely_drop=likely_drop_cards,
        )

        summary = self._build_summary(groups)
        differences = self._build_key_differences(project, selected, best_group)
        actions = self._build_actions(selected, groups)

        return {
            "summary": summary,
            "groups": groups,
            "key_differences": differences,
            "recommended_next_actions": actions,
        }

    def suggest_compare_ids(
        self,
        candidates: Iterable[CandidateListing],
        *,
        anchor_candidate_id=None,
        limit: int = 4,
    ) -> list:
        selected = [
            candidate
            for candidate in candidates
            if candidate.candidate_assessment is not None and candidate.user_decision != "rejected"
        ]
        if anchor_candidate_id is not None:
            anchor = next((candidate for candidate in selected if candidate.id == anchor_candidate_id), None)
            selected = [candidate for candidate in selected if candidate.id != anchor_candidate_id]
        else:
            anchor = None

        selected.sort(key=self._suggestion_sort_key, reverse=True)
        chosen = selected[: max(limit - (1 if anchor else 0), 0)]
        if anchor is not None:
            return [anchor.id, *[candidate.id for candidate in chosen]]
        return [candidate.id for candidate in selected[:limit]]

    def build_compare_preview(
        self,
        project: SearchProject,
        candidates: Iterable[CandidateListing],
    ) -> Optional[SuggestedComparePreview]:
        selected = list(candidates)
        candidate_ids = self.suggest_compare_ids(selected)
        if len(candidate_ids) < 2:
            return None

        candidate_map = {candidate.id: candidate for candidate in selected}
        compare_set = [candidate_map[candidate_id] for candidate_id in candidate_ids if candidate_id in candidate_map]
        if len(compare_set) < 2:
            return None

        comparison = self.compare(project=project, candidates=compare_set)
        names = [candidate.name for candidate in compare_set]
        return SuggestedComparePreview(
            candidate_ids=[candidate.id for candidate in compare_set],
            candidate_names=names,
            headline=comparison["summary"].headline,
            summary=comparison["summary"].summary,
            action_prompt="Open compare workspace to see the tradeoffs, blockers, and next actions side by side.",
        )

    def _classify_candidate(self, candidate: CandidateListing) -> str:
        assessment = candidate.candidate_assessment
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment

        if candidate.user_decision == "rejected":
            return "likely_drop"
        if assessment is None:
            return "not_ready"
        if assessment.next_best_action == "reject" or assessment.status == "recommended_reject":
            return "likely_drop"

        cost_missing = len(cost.monthly_cost_missing_items) if cost else 3
        clause_blocked = clause is not None and clause.clause_risk_flag == "high_risk"

        if (
            assessment.recommendation_confidence == "low"
            and assessment.critical_uncertainty_level == "high"
            and (
                assessment.next_best_action in {"verify_cost", "verify_clause"}
                or cost_missing >= 2
                or clause_blocked
            )
        ):
            return "not_ready"

        return "comparable"

    def _compare_strength(self, project: SearchProject, candidate: CandidateListing) -> float:
        assessment = candidate.candidate_assessment
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment
        extracted = candidate.extracted_info
        if assessment is None:
            return -999.0

        potential = {"high": 3.2, "medium": 2.2, "low": 1.0}.get(assessment.potential_value_level, 1.5)
        confidence = {"high": 2.4, "medium": 1.6, "low": 0.7}.get(assessment.recommendation_confidence, 0.7)
        clarity = {"high": 2.0, "medium": 1.2, "low": 0.4}.get(
            cost.monthly_cost_confidence if cost else "low",
            0.4,
        )
        clause_stability = {
            "none": 1.8,
            "needs_confirmation": 1.0,
            "high_risk": 0.2,
        }.get(clause.clause_risk_flag if clause else "needs_confirmation", 0.8)
        fit = self._project_fit_score(project, candidate)
        uncertainty_penalty = {"high": 1.4, "medium": 0.7, "low": 0.2}.get(
            assessment.critical_uncertainty_level,
            0.7,
        )
        risk_penalty = {"high": 1.2, "medium": 0.7, "low": 0.2}.get(assessment.decision_risk_level, 0.7)
        action_bonus = {
            "schedule_viewing": 1.2,
            "keep_warm": 0.5,
            "verify_clause": 0.2,
            "verify_cost": 0.0,
            "reject": -1.5,
        }.get(assessment.next_best_action, 0.0)

        # Keep the scoring soft. The goal is to separate a current best option
        # from viable alternatives, not to manufacture a fake precise ranking.
        return potential + confidence + clarity + clause_stability + fit + action_bonus - uncertainty_penalty - risk_penalty

    def _project_fit_score(self, project: SearchProject, candidate: CandidateListing) -> float:
        score = 0.0
        extracted = candidate.extracted_info
        cost = candidate.cost_assessment

        if extracted and extracted.district and project.preferred_districts:
            if extracted.district.lower() in {district.lower() for district in project.preferred_districts}:
                score += 1.2

        if project.max_budget is not None and cost and cost.known_monthly_cost is not None:
            if cost.known_monthly_cost <= project.max_budget:
                score += 1.4
            elif cost.known_monthly_cost <= project.max_budget * 1.08:
                score += 0.4
            else:
                score -= 1.6

        furnished_required = any(item.lower() == "furnished" for item in project.must_have)
        if furnished_required and extracted and extracted.furnished:
            if "furnished" in extracted.furnished.lower():
                score += 0.8
            else:
                score -= 0.8

        return score

    def _build_candidate_card(
        self,
        candidate: CandidateListing,
        group: str,
        best_candidate: Optional[CandidateListing],
    ) -> CompareCandidateCard:
        assessment = candidate.candidate_assessment
        extracted = candidate.extracted_info
        return CompareCandidateCard(
            candidate_id=candidate.id,
            name=candidate.name,
            compare_group=group,
            top_recommendation=assessment.top_level_recommendation if assessment else "not_ready",
            decision_explanation=self._decision_explanation(candidate, group, best_candidate),
            main_tradeoff=self._main_tradeoff(candidate, best_candidate),
            open_blocker=self._open_blocker(candidate),
            next_action=assessment.next_best_action if assessment else "verify_cost",
            monthly_rent=extracted.monthly_rent if extracted else None,
            district=extracted.district if extracted else None,
            status=candidate.status,
            benchmark=self.benchmark_service.build_for_candidate(candidate),
        )

    def _decision_explanation(
        self,
        candidate: CandidateListing,
        group: str,
        best_candidate: Optional[CandidateListing],
    ) -> str:
        assessment = candidate.candidate_assessment
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment

        if group == "best_current_option":
            strongest = self._primary_strength(candidate)
            return (
                f"This is the strongest current option because {strongest} and the case for moving forward "
                "requires less faith than the rest of the shortlist."
            )

        if group == "viable_alternative":
            anchor = best_candidate.name if best_candidate else "the current lead"
            blocker = self._open_blocker(candidate)
            if assessment and assessment.next_best_action == "verify_cost":
                return (
                    f"This candidate still has upside, but it trails {anchor} because its real cost "
                    "is less settled today."
                )
            if clause and clause.clause_risk_flag != "none":
                return (
                    f"This remains viable, but it carries more clause uncertainty than {anchor} right now."
                )
            if blocker:
                return (
                    f"This remains viable, but it still trails {anchor} because {blocker[0].lower() + blocker[1:]}."
                )
            return (
                f"This is still worth keeping in view, but it does not beat {anchor} on clarity and decision readiness."
            )

        if group == "not_ready":
            if cost and cost.cost_risk_flag in {"hidden_cost_risk", "possible_additional_cost"}:
                return (
                    "This candidate cannot be compared fairly yet because hidden or unclear costs could still "
                    "change the whole decision."
                )
            return (
                "This candidate still has enough uncertainty that putting it head-to-head with the rest would "
                "create a false sense of precision."
            )

        return (
            "This candidate currently asks for more compromise than the rest of the selected shortlist, "
            "so it should not take much of your attention right now."
        )

    def _main_tradeoff(
        self,
        candidate: CandidateListing,
        best_candidate: Optional[CandidateListing],
    ) -> str:
        assessment = candidate.candidate_assessment
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment

        if assessment is None:
            return "It still needs a first-pass assessment before any real tradeoff can be stated."

        if assessment.next_best_action == "verify_cost":
            return "The upside is still real, but the hidden-cost question is doing most of the damage."
        if assessment.next_best_action == "verify_clause":
            return "The listing may still work, but lease clarity matters more than any cosmetic upside right now."
        if assessment.next_best_action == "schedule_viewing":
            if best_candidate and best_candidate.id != candidate.id:
                return f"It is more decision-ready than {best_candidate.name}, but you still need to confirm whether it truly beats the current lead on fit."
            return "It may not be the cheapest option, but it is currently the easiest one to trust and move forward with."
        if assessment.next_best_action == "keep_warm":
            return "It stays alive because there is no fatal issue yet, but it is not creating enough urgency or clarity to push first."

        if clause and clause.move_in_date_level == "mismatch":
            return "Even if other pieces improve, the move-in timing could still make this a poor fit."
        if cost and cost.cost_risk_flag == "over_budget":
            return "Any benefit this candidate offers is being offset by cost pressure."
        return "The candidate still needs a better reason to beat the alternatives in this compare set."

    def _open_blocker(self, candidate: CandidateListing) -> Optional[str]:
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment
        assessment = candidate.candidate_assessment

        if assessment is None:
            return "No structured assessment has been generated yet."

        if cost and cost.monthly_cost_missing_items:
            if "management_fee_amount" in cost.monthly_cost_missing_items or "management_fee_included" in cost.monthly_cost_missing_items:
                return "Management fee is still unclear."
            if "rates_amount" in cost.monthly_cost_missing_items or "rates_included" in cost.monthly_cost_missing_items:
                return "Rates or government charges are still unclear."
            return "The true monthly cost is still incomplete."

        if clause:
            if clause.repair_responsibility_level in {"unknown", "unclear"}:
                return "Repair responsibility still needs to be pinned down."
            if clause.repair_responsibility_level == "supported_but_unconfirmed":
                return "Repair support looks promising, but the final responsibility still needs to be confirmed."
            if clause.lease_term_level in {"unknown", "rigid", "unstable"}:
                return "Lease flexibility is still a blocker."
            if clause.move_in_date_level in {"unknown", "uncertain", "mismatch"}:
                return "Move-in timing still needs confirmation."

        if assessment.next_best_action == "keep_warm":
            return "It is viable, but there is not a strong reason to push it ahead of the rest."
        return None

    def _build_summary(self, groups: CompareDecisionGroups) -> CompareSummary:
        best = groups.best_current_option
        viable = len(groups.viable_alternatives)
        not_ready = len(groups.not_ready_for_fair_comparison)
        likely_drop = len(groups.likely_drop)

        if best:
            viable_name = groups.viable_alternatives[0].name if groups.viable_alternatives else None
            blocked_name = (
                groups.not_ready_for_fair_comparison[0].name
                if groups.not_ready_for_fair_comparison
                else None
            )
            headline = f"{best.name} is the strongest current option"
            summary_parts = [
                f"{best.name} is leading because it currently gives you the cleanest path to a real decision."
            ]
            if viable_name:
                summary_parts.append(f"{viable_name} still deserves to stay in the shortlist, but it is asking for more compromise.")
            if blocked_name:
                summary_parts.append(f"{blocked_name} still has enough unresolved uncertainty that it cannot be judged on equal footing yet.")
            if likely_drop:
                summary_parts.append(f"{likely_drop} weaker option(s) can probably move out of your main attention.")
            summary = " ".join(summary_parts)
            confidence_note = (
                "Treat this as a current decision snapshot rather than a permanent ranking. "
                "If the unresolved blockers are cleared, the order of confidence can still change."
            )
            return CompareSummary(
                headline=headline,
                summary=summary,
                confidence_note=confidence_note,
            )

        headline = "The shortlist is still too unsettled for a clear lead"
        summary = (
            f"{not_ready} selected candidate(s) still need more validation and "
            f"{likely_drop} already look weak. Clear the blockers before trying to crown a frontrunner."
        )
        return CompareSummary(
            headline=headline,
            summary=summary,
            confidence_note="The current set is better treated as an investigation queue than a fair comparison.",
        )

    def _build_key_differences(
        self,
        project: SearchProject,
        candidates: list[CandidateListing],
        best_card: Optional[CompareCandidateCard],
    ) -> list[CompareDifference]:
        differences: list[CompareDifference] = []
        if not candidates:
            return differences

        def pick_name(items: list[CandidateListing]) -> Optional[str]:
            return items[0].name if items else None

        cost_sorted = sorted(
            [candidate for candidate in candidates if candidate.cost_assessment is not None],
            key=lambda candidate: {"high": 0, "medium": 1, "low": 2}.get(
                candidate.cost_assessment.monthly_cost_confidence,
                2,
            ),
        )
        if cost_sorted:
            clearest = pick_name(cost_sorted)
            leader_id = cost_sorted[0].id
            unclear = [
                candidate.name
                for candidate in cost_sorted
                if candidate.id != leader_id
                and candidate.cost_assessment.cost_risk_flag in {"hidden_cost_risk", "possible_additional_cost"}
            ]
            differences.append(
                CompareDifference(
                    category="cost_clarity",
                    title="Cost clarity is not evenly distributed",
                    summary=(
                        f"{clearest} currently has the clearest cost picture. "
                        + (f"{', '.join(unclear[:2])} still carry hidden-cost uncertainty." if unclear else "The rest are comparatively easier to price.")
                    ),
                )
            )

        clause_sorted = sorted(
            [candidate for candidate in candidates if candidate.clause_assessment is not None],
            key=lambda candidate: {"none": 0, "needs_confirmation": 1, "high_risk": 2}.get(
                candidate.clause_assessment.clause_risk_flag,
                1,
            ),
        )
        if clause_sorted:
            steadiest = pick_name(clause_sorted)
            leader_id = clause_sorted[0].id
            fragile = [
                candidate.name
                for candidate in clause_sorted
                if candidate.id != leader_id
                and candidate.clause_assessment.clause_risk_flag != "none"
            ]
            differences.append(
                CompareDifference(
                    category="clause_stability",
                    title="Lease stability separates the shortlist",
                    summary=(
                        f"{steadiest} looks steadier on lease terms today. "
                        + (f"{', '.join(fragile[:2])} still need more clause confirmation." if fragile else "The rest are not showing major clause friction.")
                    ),
                )
            )

        fit_sorted = sorted(candidates, key=lambda candidate: self._project_fit_score(project, candidate), reverse=True)
        if fit_sorted:
            fit_lead = fit_sorted[0].name
            differences.append(
                CompareDifference(
                    category="project_fit",
                    title="Project fit still matters as much as price",
                    summary=(
                        f"{fit_lead} currently fits the project constraints best based on budget, district, and stated must-haves."
                    ),
                )
            )

        if best_card:
            low_conf = [
                candidate.name
                for candidate in candidates
                if candidate.id != best_card.candidate_id
                and candidate.candidate_assessment
                and candidate.candidate_assessment.recommendation_confidence == "low"
            ]
            differences.append(
                CompareDifference(
                    category="decision_confidence",
                    title="Some candidates still look weaker because they are harder to trust",
                    summary=(
                        f"{best_card.name} is not just the strongest on paper; it is also easier to trust today. "
                        + (f"{', '.join(low_conf[:2])} would benefit most from more evidence." if low_conf else "The rest are relatively close on confidence.")
                    ),
                )
            )

        return differences[:4]

    def _build_actions(
        self,
        candidates: list[CandidateListing],
        groups: CompareDecisionGroups,
    ) -> CompareRecommendedActions:
        questions = [
            item.question
            for item in self.dashboard_service.build_investigation_items(candidates)
        ]
        deduped_questions: list[str] = []
        for question in questions:
            if question not in deduped_questions:
                deduped_questions.append(question)

        contact_first = None
        if groups.best_current_option is not None:
            contact_first = CompareActionTarget(
                candidate_id=groups.best_current_option.candidate_id,
                name=groups.best_current_option.name,
                reason="It is the current lead, so every new piece of evidence here has the best chance of moving you toward a real decision.",
            )
        elif groups.not_ready_for_fair_comparison:
            first = groups.not_ready_for_fair_comparison[0]
            contact_first = CompareActionTarget(
                candidate_id=first.candidate_id,
                name=first.name,
                reason="This candidate has enough upside that clearing its main blocker could reshape the compare set.",
            )

        viewing_candidate = None
        viewing_pool = []
        if groups.best_current_option and groups.best_current_option.next_action == "schedule_viewing":
            viewing_pool.append(groups.best_current_option)
        viewing_pool.extend(card for card in groups.viable_alternatives if card.next_action == "schedule_viewing")
        if viewing_pool:
            viewing_candidate = CompareActionTarget(
                candidate_id=viewing_pool[0].candidate_id,
                name=viewing_pool[0].name,
                reason="This candidate is already clear enough that a viewing could move the decision forward.",
            )

        deprioritize = [
            CompareActionTarget(
                candidate_id=card.candidate_id,
                name=card.name,
                reason=card.decision_explanation,
            )
            for card in groups.likely_drop[:2]
        ]

        return CompareRecommendedActions(
            contact_first=contact_first,
            questions_to_ask=deduped_questions[:4],
            viewing_candidate=viewing_candidate,
            deprioritize=deprioritize,
        )

    def _primary_strength(self, candidate: CandidateListing) -> str:
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment
        assessment = candidate.candidate_assessment
        extracted = candidate.extracted_info

        if cost and cost.monthly_cost_confidence == "high" and cost.cost_risk_flag == "none":
            return "its cost picture is clearer than the rest"
        if clause and clause.clause_risk_flag == "none":
            return "its lease posture is steadier than the rest"
        if extracted and extracted.district:
            return f"it already looks like a cleaner fit around {extracted.district}"
        if assessment and assessment.recommendation_confidence == "high":
            return "it is easier to trust with the information available today"
        return "it is easier to trust with the information available today"

    def _suggestion_sort_key(self, candidate: CandidateListing) -> tuple:
        assessment = candidate.candidate_assessment
        if assessment is None:
            return (0, 0, 0, 0)
        shortlist_bias = 1 if candidate.user_decision == "shortlisted" else 0
        recommendation_bias = {
            "shortlist_recommendation": 3,
            "not_ready": 2,
            "likely_reject": 1,
        }.get(assessment.top_level_recommendation, 1)
        confidence = {"high": 3, "medium": 2, "low": 1}.get(assessment.recommendation_confidence, 1)
        potential = {"high": 3, "medium": 2, "low": 1}.get(assessment.potential_value_level, 1)
        return (shortlist_bias, recommendation_bias, confidence, potential)
