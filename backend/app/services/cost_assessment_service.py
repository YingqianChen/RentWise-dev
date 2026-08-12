"""Cost assessment service for analyzing rental costs."""

from __future__ import annotations

import re
from typing import List, Optional

from ..db.models import CandidateExtractedInfo, CostAssessment


def parse_monetary_amount(value: Optional[str]) -> Optional[float]:
    """Parse monetary amount from free-form text."""
    if not value or str(value).strip().lower() in {"unknown", "n/a", "none", ""}:
        return None
    cleaned = str(value).replace("$", "").replace("HKD", "").replace(",", "").strip()
    match = re.search(r"[\d.]+", cleaned)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def parse_months_value(value: Optional[str]) -> Optional[float]:
    """Parse values like '2 months' or 'half month' from text."""
    if not value or str(value).strip().lower() in {"unknown", "n/a", "none", ""}:
        return None
    lower = str(value).lower()
    if "half" in lower:
        return 0.5
    match = re.search(r"(\d+(?:\.\d+)?)", lower)
    return float(match.group()) if match else None


class CostAssessmentService:
    """Build cost assessment from extracted listing fields."""

    def assess(
        self,
        extracted_info: CandidateExtractedInfo,
        max_budget: Optional[int] = None,
        source_text: str = "",
    ) -> CostAssessment:
        monthly_rent = parse_monetary_amount(extracted_info.monthly_rent)
        management_fee = parse_monetary_amount(extracted_info.management_fee_amount)
        rates = parse_monetary_amount(extracted_info.rates_amount)
        deposit_months = parse_months_value(extracted_info.deposit)
        agent_fee_months = parse_months_value(extracted_info.agent_fee)

        missing_items: List[str] = []
        known_monthly_cost: Optional[float] = None
        monthly_cost_confidence = "low"

        if monthly_rent is not None:
            components = [monthly_rent]
            monthly_missing = []

            if extracted_info.management_fee_included is True:
                pass
            elif extracted_info.management_fee_included is False and management_fee is not None:
                components.append(management_fee)
            elif extracted_info.management_fee_included is False:
                monthly_missing.append("management_fee_amount")
                missing_items.append("management_fee_amount")
            else:
                monthly_missing.append("management_fee_included")
                missing_items.append("management_fee_included")

            if extracted_info.rates_included is True:
                pass
            elif extracted_info.rates_included is False and rates is not None:
                components.append(rates)
            elif extracted_info.rates_included is False:
                monthly_missing.append("rates_amount")
                missing_items.append("rates_amount")
            else:
                monthly_missing.append("rates_included")
                missing_items.append("rates_included")

            known_monthly_cost = sum(components)
            if not monthly_missing:
                monthly_cost_confidence = "high"
            elif len(monthly_missing) == 1:
                monthly_cost_confidence = "medium"
            else:
                monthly_cost_confidence = "low"
        else:
            missing_items.append("monthly_rent")

        move_in_cost_known_part: Optional[float] = None
        move_in_cost_confidence = "low"
        if monthly_rent is not None:
            components = [monthly_rent]
            if deposit_months is not None:
                components.append(monthly_rent * deposit_months)
            else:
                missing_items.append("deposit")
            if agent_fee_months is not None:
                components.append(monthly_rent * agent_fee_months)
            else:
                missing_items.append("agent_fee")
            move_in_cost_known_part = sum(components)
            if deposit_months is not None and agent_fee_months is not None:
                move_in_cost_confidence = "high"
            elif deposit_months is not None or agent_fee_months is not None:
                move_in_cost_confidence = "medium"

        cost_risk_flag = self._determine_risk_flag(
            known_monthly_cost=known_monthly_cost,
            monthly_cost_confidence=monthly_cost_confidence,
            missing_items=missing_items,
            max_budget=max_budget,
            extracted_info=extracted_info,
            source_text=source_text,
        )
        summary = self._generate_summary(
            known_monthly_cost=known_monthly_cost,
            cost_risk_flag=cost_risk_flag,
            missing_items=missing_items,
        )

        return CostAssessment(
            candidate_id=extracted_info.candidate_id,
            known_monthly_cost=known_monthly_cost,
            monthly_cost_confidence=monthly_cost_confidence,
            monthly_cost_missing_items=sorted(set(missing_items)),
            move_in_cost_known_part=move_in_cost_known_part,
            move_in_cost_confidence=move_in_cost_confidence,
            cost_risk_flag=cost_risk_flag,
            summary=summary,
        )

    def _determine_risk_flag(
        self,
        known_monthly_cost: Optional[float],
        monthly_cost_confidence: str,
        missing_items: List[str],
        max_budget: Optional[int],
        extracted_info: CandidateExtractedInfo,
        source_text: str,
    ) -> str:
        if (
            max_budget
            and known_monthly_cost
            and known_monthly_cost > max_budget
            and self._monthly_cost_is_source_backed(extracted_info, source_text)
        ):
            return "over_budget"
        explicitly_separate_unknown = any(
            item in {"management_fee_amount", "rates_amount"}
            for item in missing_items
        )
        if explicitly_separate_unknown:
            return "possible_additional_cost"
        if missing_items or monthly_cost_confidence == "low":
            return "incomplete"
        if max_budget and known_monthly_cost and known_monthly_cost > max_budget:
            return "incomplete"
        return "none"

    def _monthly_cost_is_source_backed(
        self,
        extracted_info: CandidateExtractedInfo,
        source_text: str,
    ) -> bool:
        if not self._amount_is_source_backed(extracted_info.monthly_rent, source_text):
            return False

        for amount, included in (
            (extracted_info.management_fee_amount, extracted_info.management_fee_included),
            (extracted_info.rates_amount, extracted_info.rates_included),
        ):
            if included is False and parse_monetary_amount(amount) is not None:
                if not self._amount_is_source_backed(amount, source_text):
                    return False
        return True

    def _amount_is_source_backed(self, value: Optional[str], source_text: str) -> bool:
        amount = parse_monetary_amount(value)
        if amount is None:
            return False
        source_amounts = (
            parse_monetary_amount(match)
            for match in re.findall(
                r"(?:HKD\s*|\$\s*)?\d[\d,]*(?:\.\d+)?",
                source_text,
                re.IGNORECASE,
            )
        )
        return any(source_amount == amount for source_amount in source_amounts)

    def _generate_summary(
        self,
        known_monthly_cost: Optional[float],
        cost_risk_flag: str,
        missing_items: List[str],
    ) -> str:
        if known_monthly_cost is None:
            return "The monthly cost cannot be estimated yet. Confirm the rent and extra fees first."

        parts = [f"The confirmed monthly cost floor is about HKD {known_monthly_cost:,.0f}."]
        if cost_risk_flag == "over_budget":
            parts.append("The known cost already exceeds the stated budget.")
        elif cost_risk_flag == "incomplete":
            parts.append("Some cost information has not been stated yet.")
        elif cost_risk_flag == "possible_additional_cost":
            parts.append("There may still be extra charges that have not been confirmed.")

        if missing_items:
            parts.append(f"Missing cost fields: {', '.join(sorted(set(missing_items))[:3])}.")
        return " ".join(parts)
