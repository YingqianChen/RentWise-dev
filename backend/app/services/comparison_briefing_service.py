"""LLM-assisted compare briefing with deterministic fallback."""

from __future__ import annotations

import logging

from typing import Iterable

from ..db.models import CandidateListing, SearchProject
from ..integrations.llm.prompts import COMPARE_BRIEFING_PROMPT
from ..integrations.llm.utils import chat_completion_json
from ..schemas.comparison import (
    CompareActionTarget,
    CompareAgentBriefing,
    CompareCandidateCard,
    CompareDecisionGroups,
    CompareDifference,
    CompareRecommendedActions,
    CompareSummary,
)

logger = logging.getLogger(__name__)


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
        fallback = self._fallback_briefing(
            summary=summary,
            groups=groups,
            recommended_actions=recommended_actions,
        )

        prompt = COMPARE_BRIEFING_PROMPT.format(
            project_context=self._project_context(project),
            compare_summary=self._compare_summary(summary),
            decision_groups=self._decision_groups(groups),
            key_differences=self._differences(key_differences),
            recommended_actions=self._recommended_actions(recommended_actions),
        )

        try:
            data = await chat_completion_json(
                prompt=prompt,
                temperature=0.2,
                max_tokens=350,
            )
            return CompareAgentBriefing(
                current_take=self._clean_field(data.get("current_take"), fallback.current_take),
                why_now=self._clean_field(data.get("why_now"), fallback.why_now),
                what_could_change=self._clean_field(data.get("what_could_change"), fallback.what_could_change),
                today_s_move=self._clean_field(data.get("today_s_move"), fallback.today_s_move),
                confidence_note=self._clean_field(data.get("confidence_note"), fallback.confidence_note),
            )
        except Exception as exc:
            logger.error("Compare briefing generation failed: %s", exc)
            return fallback

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
                    f"It is ahead because the rest of the selected set is either too uncertain or too weak to challenge it right now."
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

    def _compare_summary(self, summary: CompareSummary) -> str:
        return (
            f"Headline: {summary.headline}\n"
            f"Summary: {summary.summary}\n"
            f"Confidence note: {summary.confidence_note}"
        )

    def _decision_groups(self, groups: CompareDecisionGroups) -> str:
        lines: list[str] = []
        if groups.best_current_option is not None:
            lines.append(self._card_line("Best current option", groups.best_current_option))
        for card in groups.viable_alternatives:
            lines.append(self._card_line("Viable alternative", card))
        for card in groups.not_ready_for_fair_comparison:
            lines.append(self._card_line("Not ready", card))
        for card in groups.likely_drop:
            lines.append(self._card_line("Likely drop", card))
        return "\n".join(lines) if lines else "No decision groups available"

    def _card_line(self, prefix: str, card: CompareCandidateCard) -> str:
        blocker = f" | blocker: {card.open_blocker}" if card.open_blocker else ""
        return (
            f"{prefix}: {card.name} | recommendation: {card.top_recommendation} | "
            f"action: {card.next_action} | why: {card.decision_explanation} | "
            f"tradeoff: {card.main_tradeoff}{blocker}"
        )

    def _differences(self, differences: list[CompareDifference]) -> str:
        if not differences:
            return "No key differences available"
        return "\n".join(f"- {item.title}: {item.summary}" for item in differences)

    def _recommended_actions(self, actions: CompareRecommendedActions) -> str:
        parts: list[str] = []
        if actions.contact_first is not None:
            parts.append(self._action_target("Contact first", actions.contact_first))
        if actions.viewing_candidate is not None:
            parts.append(self._action_target("Viewing candidate", actions.viewing_candidate))
        if actions.questions_to_ask:
            parts.append("Questions: " + " | ".join(actions.questions_to_ask))
        if actions.deprioritize:
            parts.append(
                "Deprioritize: "
                + " | ".join(f"{item.name} ({item.reason})" for item in actions.deprioritize)
            )
        return "\n".join(parts) if parts else "No recommended actions available"

    def _action_target(self, label: str, target: CompareActionTarget) -> str:
        return f"{label}: {target.name} - {target.reason}"

    def _clean_field(self, value: object, fallback: str) -> str:
        if not isinstance(value, str):
            return fallback
        cleaned = " ".join(value.split())
        return cleaned if cleaned else fallback
