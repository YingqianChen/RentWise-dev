"""Dashboard aggregation service."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Tuple
from uuid import UUID, uuid5, NAMESPACE_URL

from ..db.models import CandidateListing, SearchProject
from ..schemas.dashboard import CandidateStats, InvestigationItemSummary, PriorityCandidate
from .candidate_analysis_state import PROCESSING_STAGES, has_usable_analysis
from .candidate_field_read_service import candidate_field_state
from .priority_service import PriorityService


@dataclass
class _GroupedInvestigationTask:
    category: str
    slug: str
    title_prefix: str
    question: str
    priority: str
    candidates: list[CandidateListing]


class DashboardService:
    """Build dashboard data from the current candidate pool."""

    def __init__(self) -> None:
        self.priority_service = PriorityService()

    def build_stats(self, candidates: Iterable[CandidateListing]) -> CandidateStats:
        """Summarize candidate and user-decision counts."""
        candidates = list(candidates)
        usable_candidates = [candidate for candidate in candidates if has_usable_analysis(candidate)]
        status_counts = Counter(
            candidate.candidate_assessment.status
            for candidate in usable_candidates
            if candidate.candidate_assessment is not None
        )
        shortlisted = sum(1 for candidate in candidates if candidate.user_decision == "shortlisted")
        rejected = sum(1 for candidate in candidates if candidate.user_decision == "rejected")
        return CandidateStats(
            total=len(candidates),
            new=status_counts.get("new", 0),
            needs_info=status_counts.get("needs_info", 0),
            follow_up=status_counts.get("follow_up", 0),
            high_risk_pending=status_counts.get("high_risk_pending", 0),
            recommended_reject=status_counts.get("recommended_reject", 0),
            shortlisted=shortlisted,
            rejected=rejected,
            processing=sum(1 for candidate in candidates if candidate.processing_stage in PROCESSING_STAGES),
            analysis_failed=sum(1 for candidate in candidates if candidate.processing_stage == "failed"),
        )

    def build_priority_candidates(self, candidates: Iterable[CandidateListing]) -> list[PriorityCandidate]:
        """Create the top priority candidate cards."""
        candidates = [
            candidate
            for candidate in candidates
            if candidate.user_decision == "undecided" and has_usable_analysis(candidate)
        ]
        if not candidates:
            return []

        ranked = self.priority_service.rank([candidate.candidate_assessment for candidate in candidates])
        candidate_map = {candidate.id: candidate for candidate in candidates}

        priority_candidates: list[PriorityCandidate] = []
        for candidate_id, score in ranked[:3]:
            candidate = candidate_map[candidate_id]
            extracted = candidate.extracted_info
            assessment = candidate.candidate_assessment
            priority_candidates.append(
                PriorityCandidate(
                    id=candidate.id,
                    name=candidate.name,
                    status=candidate.status,
                    potential_value_level=assessment.potential_value_level,
                    completeness_level=assessment.completeness_level,
                    next_best_action=assessment.next_best_action,
                    monthly_rent=extracted.monthly_rent if extracted else None,
                    district=extracted.district if extracted else None,
                    reason=self._build_priority_reason(candidate),
                    priority_score=round(score, 2),
                )
            )
        return priority_candidates

    def build_investigation_items(
        self,
        candidates: Iterable[CandidateListing],
    ) -> list[InvestigationItemSummary]:
        """Generate an action-oriented investigation checklist."""
        ranked_candidates = self._rank_candidates_for_checklist(candidates)
        grouped_tasks: dict[tuple[str, str, str], _GroupedInvestigationTask] = {}

        for candidate, _score in ranked_candidates:
            assessment = candidate.candidate_assessment
            if candidate.user_decision != "undecided" or assessment is None:
                continue

            cost = candidate.cost_assessment
            clause = candidate.clause_assessment

            if cost is not None:
                self._add_grouped_tasks(grouped_tasks, self._build_cost_tasks(candidate, cost))
            if clause is not None:
                self._add_grouped_tasks(grouped_tasks, self._build_clause_tasks(candidate, clause))

            if assessment.next_best_action == "schedule_viewing":
                self._add_grouped_tasks(
                    grouped_tasks,
                    [
                        _GroupedInvestigationTask(
                            category="timing",
                            slug="viewing",
                            title_prefix="Decide whether to book a viewing",
                            question="This candidate is stable enough for follow-up. Decide whether it deserves a viewing slot now.",
                            priority="medium",
                            candidates=[candidate],
                        )
                    ],
                )

        items = self._materialize_grouped_tasks(grouped_tasks)
        items.sort(key=self._investigation_sort_key)
        return items[:10]

    def build_current_advice(
        self,
        project: SearchProject,
        stats: CandidateStats,
        priority_candidates: list[PriorityCandidate],
        open_items: list[InvestigationItemSummary],
    ) -> str:
        """Build a short deterministic dashboard summary."""
        if stats.total == 0:
            return (
                f"Start by importing listings into '{project.title}'. "
                "The system will organize the candidate pool and surface the next best actions."
            )

        if stats.analysis_failed and not priority_candidates and not open_items:
            return (
                f"{stats.analysis_failed} candidate analysis failed. "
                "Retry the analysis or edit the source information before relying on a recommendation."
            )

        if stats.processing and not priority_candidates and not open_items:
            return (
                f"{stats.processing} candidate analysis is still processing. "
                "Wait for it to finish before comparing options or acting on a recommendation."
            )

        if priority_candidates:
            top = priority_candidates[0]
            if top.next_best_action == "verify_cost":
                return (
                    f"{top.name} should be handled first. "
                    "It has upside, but you still need to verify the real cost before trusting it."
                )
            if top.next_best_action == "verify_clause":
                return (
                    f"{top.name} is the best next investigation target. "
                    "The core lease terms are still the main blocker."
                )
            if top.next_best_action == "schedule_viewing":
                return (
                    f"{top.name} is currently the strongest stable option. "
                    "It looks ready for a viewing or serious follow-up."
                )
            if top.next_best_action == "keep_warm":
                return (
                    f"{top.name} is still alive in the pool, but it is not the first thing to push today."
                )
            if top.next_best_action == "reject":
                return (
                    "The current pool still has weak or risky options. "
                    "Clear out the worst candidates so your attention goes to stronger ones."
                )

        if open_items:
            return (
                f"There are still {len(open_items)} open investigation tasks. "
                "Clear the high-priority blockers before making shortlist decisions."
            )

        return (
            "The candidate pool now has a usable first-pass assessment. "
            "You can keep adding information or confirm shortlist decisions."
        )

    def _rank_candidates_for_checklist(self, candidates: Iterable[CandidateListing]) -> List[Tuple[CandidateListing, float]]:
        active_candidates = [
            candidate
            for candidate in candidates
            if candidate.user_decision == "undecided" and has_usable_analysis(candidate)
        ]
        if not active_candidates:
            return []

        ranked = self.priority_service.rank([candidate.candidate_assessment for candidate in active_candidates])
        candidate_map = {candidate.id: candidate for candidate in active_candidates}
        return [(candidate_map[candidate_id], score) for candidate_id, score in ranked]

    def _build_cost_tasks(self, candidate: CandidateListing, cost) -> list[_GroupedInvestigationTask]:
        tasks: list[_GroupedInvestigationTask] = []
        missing = set(cost.monthly_cost_missing_items)

        if "monthly_rent" in missing:
            tasks.append(
                _GroupedInvestigationTask(
                    category="cost",
                    slug="rent",
                    title_prefix="Confirm the quoted rent",
                    question=self._with_field_state_note(
                        candidate,
                        ["monthly_rent"],
                        "You cannot compare these candidates fairly until the quoted monthly rent is explicit.",
                    ),
                    priority="high",
                    candidates=[candidate],
                )
            )
        if "management_fee_amount" in missing or "management_fee_included" in missing:
            tasks.append(
                _GroupedInvestigationTask(
                    category="cost",
                    slug="management",
                    title_prefix="Clarify the management fee",
                    question=self._with_field_state_note(
                        candidate,
                        ["management_fee_included", "management_fee_amount"],
                        "Ask whether the management fee is included and, if not, how much it adds each month.",
                    ),
                    priority="high",
                    candidates=[candidate],
                )
            )
        if "rates_amount" in missing or "rates_included" in missing:
            is_cost_incomplete = cost.cost_risk_flag == "incomplete"
            tasks.append(
                _GroupedInvestigationTask(
                    category="cost",
                    slug="rates",
                    title_prefix=(
                        "Clarify whether rates or government charges are included"
                        if is_cost_incomplete
                        else "Confirm the expected amount of separate rates or government charges"
                    ),
                    question=self._with_field_state_note(
                        candidate,
                        ["rates_included", "rates_amount"],
                        "Ask whether rates are included at all. Until that is clear, the true monthly cost could still shift."
                        if is_cost_incomplete
                        else "Ask what the expected monthly amount is for rates or government charges so you can tighten the cost estimate.",
                    ),
                    priority="high" if is_cost_incomplete else "medium",
                    candidates=[candidate],
                )
            )
        if "deposit" in missing:
            tasks.append(
                _GroupedInvestigationTask(
                    category="cost",
                    slug="deposit",
                    title_prefix="Confirm deposit expectations",
                    question=self._with_field_state_note(
                        candidate,
                        ["deposit"],
                        "Find out how many months of deposit are required so you can gauge the upfront cash burden.",
                    ),
                    priority="medium",
                    candidates=[candidate],
                )
            )
        if "agent_fee" in missing:
            tasks.append(
                _GroupedInvestigationTask(
                    category="cost",
                    slug="agent-fee",
                    title_prefix="Check whether there is an agent fee",
                    question=self._with_field_state_note(
                        candidate,
                        ["agent_fee"],
                        "Confirm whether an agent fee applies and how much it adds to move-in cost.",
                    ),
                    priority="medium",
                    candidates=[candidate],
                )
            )

        return tasks

    def _build_clause_tasks(self, candidate: CandidateListing, clause) -> list[_GroupedInvestigationTask]:
        tasks: list[_GroupedInvestigationTask] = []

        if clause.repair_responsibility_level in {"unknown", "unclear"}:
            tasks.append(
                _GroupedInvestigationTask(
                    category="clause",
                    slug="repair",
                    title_prefix="Clarify repair responsibility",
                    question=self._with_field_state_note(
                        candidate,
                        ["repair_responsibility"],
                        "Ask which repairs the landlord covers and which costs could fall on the tenant.",
                    ),
                    priority="high",
                    candidates=[candidate],
                )
            )
        elif clause.repair_responsibility_level == "supported_but_unconfirmed":
            tasks.append(
                _GroupedInvestigationTask(
                    category="clause",
                    slug="repair-support",
                    title_prefix="Confirm repair coverage in writing",
                    question="There is a positive signal that repair support exists, but confirm who is contractually responsible and what exactly is covered.",
                    priority="medium",
                    candidates=[candidate],
                )
            )
        elif clause.repair_responsibility_level == "tenant_heavy":
            tasks.append(
                _GroupedInvestigationTask(
                    category="clause",
                    slug="tenant-heavy-repair",
                    title_prefix="Validate the repair burden",
                    question="The current wording suggests the tenant may carry too much repair risk. Confirm the exact scope before proceeding.",
                    priority="high",
                    candidates=[candidate],
                )
            )

        if clause.lease_term_level in {"unknown", "rigid", "unstable"}:
            tasks.append(
                _GroupedInvestigationTask(
                    category="clause",
                    slug="lease-term",
                    title_prefix="Confirm lease flexibility",
                    question=self._with_field_state_note(
                        candidate,
                        ["lease_term"],
                        "Ask about lease length, break clause, and early termination terms so you understand how rigid the commitment is.",
                    ),
                    priority="medium" if clause.lease_term_level == "rigid" else "high",
                    candidates=[candidate],
                )
            )

        if clause.move_in_date_level in {"unknown", "uncertain", "mismatch"}:
            tasks.append(
                _GroupedInvestigationTask(
                    category="timing",
                    slug="move-in",
                    title_prefix="Confirm move-in timing",
                    question=self._with_field_state_note(
                        candidate,
                        ["move_in_date"],
                        "Ask for the earliest realistic move-in date and whether it still fits your own timeline.",
                    ),
                    priority="high" if clause.move_in_date_level == "mismatch" else "medium",
                    candidates=[candidate],
                )
            )

        return tasks

    def _with_field_state_note(
        self,
        candidate: CandidateListing,
        field_keys: list[str],
        question: str,
    ) -> str:
        states = {candidate_field_state(candidate, field_key) for field_key in field_keys}
        if "conflicted" in states:
            return f"{question} The supplied sources currently disagree on this point."
        if "inferred" in states:
            return f"{question} The current value is only inferred, not directly stated."
        return question

    def _add_grouped_tasks(
        self,
        grouped_tasks: dict[tuple[str, str, str], _GroupedInvestigationTask],
        tasks: list[_GroupedInvestigationTask],
    ) -> None:
        for task in tasks:
            key = (task.category, task.slug, task.priority)
            if key not in grouped_tasks:
                grouped_tasks[key] = _GroupedInvestigationTask(
                    category=task.category,
                    slug=task.slug,
                    title_prefix=task.title_prefix,
                    question=task.question,
                    priority=task.priority,
                    candidates=list(task.candidates),
                )
            else:
                grouped_tasks[key].candidates.extend(task.candidates)

    def _materialize_grouped_tasks(
        self,
        grouped_tasks: dict[tuple[str, str, str], _GroupedInvestigationTask],
    ) -> list[InvestigationItemSummary]:
        items: list[InvestigationItemSummary] = []
        for task in grouped_tasks.values():
            ordered_candidates = self._unique_candidates(task.candidates)
            candidate_names = [candidate.name for candidate in ordered_candidates]
            item_id = self._make_group_item_id(
                ordered_candidates[0].project_id,
                task.category,
                task.slug,
                candidate_names,
            )
            items.append(
                InvestigationItemSummary(
                    id=item_id,
                    candidate_id=ordered_candidates[0].id if len(ordered_candidates) == 1 else None,
                    category=task.category,
                    title=self._group_task_title(task.title_prefix, candidate_names),
                    question=self._group_task_question(task.question, candidate_names),
                    priority=task.priority,
                    status="open",
                )
            )
        return items

    def _group_task_title(self, title_prefix: str, candidate_names: list[str]) -> str:
        if len(candidate_names) == 1:
            return f"{title_prefix} for {candidate_names[0]}"
        if len(candidate_names) == 2:
            return f"{title_prefix} for {candidate_names[0]} and {candidate_names[1]}"
        return f"{title_prefix} for {len(candidate_names)} candidates"

    def _group_task_question(self, question: str, candidate_names: list[str]) -> str:
        if len(candidate_names) == 1:
            return question
        if len(candidate_names) <= 3:
            names = ", ".join(candidate_names[:-1]) + f", and {candidate_names[-1]}" if len(candidate_names) > 2 else " and ".join(candidate_names)
            return f"{question} This applies to {names}."
        return f"{question} This applies to {len(candidate_names)} candidates in the current pool."

    def _unique_candidates(self, candidates: list[CandidateListing]) -> list[CandidateListing]:
        seen: set[UUID] = set()
        unique: list[CandidateListing] = []
        for candidate in candidates:
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            unique.append(candidate)
        return unique

    def _make_group_item_id(
        self,
        project_id: UUID,
        category: str,
        slug: str,
        candidate_names: list[str],
    ) -> UUID:
        joined = "|".join(candidate_names)
        return uuid5(NAMESPACE_URL, f"grouped:{project_id}:{category}:{slug}:{joined}")

    def _build_priority_reason(self, candidate: CandidateListing) -> str:
        assessment = candidate.candidate_assessment
        cost = candidate.cost_assessment
        clause = candidate.clause_assessment

        if assessment is None:
            return "This candidate still needs a fresh assessment."

        if assessment.next_best_action == "verify_cost":
            if cost and cost.monthly_cost_missing_items:
                missing = ", ".join(cost.monthly_cost_missing_items[:2])
                return f"It has upside, but you still need to confirm {missing}."
            return "It has upside, but the real monthly cost is still unclear."

        if assessment.next_best_action == "verify_clause":
            if clause and clause.repair_responsibility_level == "tenant_heavy":
                return "The repair burden may be too tenant-heavy, so the lease terms need checking first."
            if clause and clause.move_in_date_level in {"unknown", "uncertain", "mismatch"}:
                return "It looks viable, but move-in timing is still a blocker."
            return "It is worth pursuing, but the key lease terms are still incomplete."

        if assessment.next_best_action == "schedule_viewing":
            return "This is currently one of the clearest and most stable options in the pool."

        if assessment.next_best_action == "keep_warm":
            return "The candidate is still viable, but another option deserves attention first."

        return "The current signals suggest your time is better spent on stronger options."

    def _make_item_id(self, candidate_id: UUID, category: str, suffix: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"{candidate_id}:{category}:{suffix}")

    def _investigation_sort_key(self, item: InvestigationItemSummary):
        priority_order = {"high": 0, "medium": 1, "low": 2}
        category_order = {"cost": 0, "clause": 1, "timing": 2, "match": 3}
        return (
            priority_order.get(item.priority, 9),
            category_order.get(item.category, 9),
            item.title,
        )
