"""Compare briefing derived locally from the evaluated candidate groups."""

from __future__ import annotations


from typing import Iterable

from ..db.models import CandidateListing, SearchProject
from ..schemas.comparison import (
    CompareAgentBriefing,
    CompareDecisionGroups,
    CompareDifference,
    CompareRecommendedActions,
    CompareSummary,
)

class ComparisonBriefingService:
    """Build a top-level compare briefing without changing compare outcomes."""

    async def build(
        self,
        *,
        project: SearchProject,
        candidates: Iterable[CandidateListing],
        summary: CompareSummary,
        groups: CompareDecisionGroups,
        key_differences: list[CompareDifference],
        recommended_actions: CompareRecommendedActions,
    ) -> CompareAgentBriefing:
        # A page refresh must not invoke AI or paraphrase deterministic outcomes
        # into a stronger recommendation than the evidence supports.
        return self._fallback_briefing(summary=summary, groups=groups, recommended_actions=recommended_actions)

    def _fallback_briefing(
        self,
        *,
        summary: CompareSummary,
        groups: CompareDecisionGroups,
        recommended_actions: CompareRecommendedActions,
    ) -> CompareAgentBriefing:
        best = groups.best_current_option
        viable = groups.viable_alternatives
        not_ready = groups.not_ready_for_fair_comparison
        likely_drop = groups.likely_drop

        if best is not None:
            current_take = (
                f"{best.name} is the current lead because it gives you the cleanest path to a real decision today."
            )
            if viable:
                why_now = (
                    f"It is ahead because the shortlist alternatives still ask for more compromise or carry weaker decision readiness than {best.name}."
                )
            else:
                why_now = (
                    "It is ahead because the rest of the selected set is either too uncertain or too weak to challenge it right now."
                )
            if not_ready:
                what_could_change = (
                    f"{not_ready[0].name} is the most likely to move the picture if its blocker is cleared: {not_ready[0].open_blocker or 'its main uncertainty still needs to be resolved.'}"
                )
            elif viable:
                what_could_change = (
                    f"{viable[0].name} could close the gap if its current tradeoff improves or one more strong piece of evidence arrives."
                )
            else:
                what_could_change = "The picture is relatively stable, but any new information about cost or lease friction could still change the order of confidence."
        else:
            current_take = "There is no reliable lead yet because this compare set still behaves more like an investigation queue than a final shortlist."
            why_now = "The current candidates are either too uncertain to compare fairly or too weak to earn priority over the rest."
            if not_ready:
                what_could_change = (
                    f"The fastest way to improve this compare is to clear the main blocker on {not_ready[0].name}: {not_ready[0].open_blocker or 'it still needs a cleaner read.'}"
                )
            else:
                what_could_change = "This compare needs stronger evidence before a lead can emerge."

        if recommended_actions.contact_first is not None:
            today_s_move = (
                f"Start with {recommended_actions.contact_first.name}: {recommended_actions.contact_first.reason}"
            )
        elif recommended_actions.questions_to_ask:
            today_s_move = f"Use today to resolve the biggest blocker first: {recommended_actions.questions_to_ask[0]}"
        elif likely_drop:
            today_s_move = (
                f"Reduce noise by deprioritizing {likely_drop[0].name} and keep your attention on the stronger options."
            )
        else:
            today_s_move = "Hold this set together, but focus on gathering one more decisive piece of evidence before pushing a final choice."

        return CompareAgentBriefing(
            current_take=current_take,
            why_now=why_now,
            what_could_change=what_could_change,
            today_s_move=today_s_move,
            confidence_note=summary.confidence_note,
        )
