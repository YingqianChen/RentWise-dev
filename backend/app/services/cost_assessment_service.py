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
    if re.search(r"(?:half[ -]?(?:a[ -]?)?month|半(?:個)?月|半佣)", lower):
        return 0.5
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:months?\b|個?月)", lower)
    if match:
        return float(match.group(1))
    numerals = {"一": 1, "二": 2, "兩": 2, "两": 2, "三": 3, "四": 4, "one": 1, "two": 2, "three": 3}
    match = re.search(r"(one|two|three)\s+months?\b|([一二兩两三四])個?月|[押按]([一二兩两三四]|\d)(?:[按押付上]|$)|([一二兩两三四])按", lower)
    if match:
        token = next(group for group in match.groups() if group is not None)
        return float(numerals[token]) if token in numerals else float(token)
    return None


def parse_upfront_amount(value: Optional[str], monthly_rent: float) -> Optional[float]:
    """Distinguish a currency amount, an explicit rent multiple and an unknown."""
    text = str(value or "").strip().lower()
    if text in {"0", "0.0", "none", "no agency fee", "no agency fees", "no commission", "免佣", "免佣金", "免按金", "no deposit"}:
        return 0.0
    # Ranges/alternatives are not an agreed amount.
    if re.search(r"\d\s*[-–~至]\s*\d|\bor\b|或", text):
        return None
    currency = re.search(r"(?:hkd?|\$)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:港元|元)", text)
    if currency:
        return float(next(group for group in currency.groups() if group).replace(",", ""))
    months = parse_months_value(value)
    return monthly_rent * months if months is not None else None


def rates_billing_period(facts) -> str:
    """Read a rates period only from its own evidence or an explicit user entry.

    Corrected rates amounts use the monthly-equivalent input contract. A plain
    model amount without a billing period remains unresolved, never assumed monthly.
    """
    fact = next((item for item in facts if item.field_key == "rates_amount"), None)
    if fact is None:
        return "unknown"
    if fact.user_action == "corrected":
        return "month"
    if fact.user_action is not None:
        # Confirmation freezes a value, not its billing period. Do not borrow
        # the period from later extraction evidence for an older confirmed sum.
        return "unknown"
    periods = set()
    for claim in fact.evidence:
        if claim.claim_kind != "explicit":
            continue
        quote = claim.quote.lower()
        # Restrict to the clause about rates so management /month cannot supply
        # the billing period for rates in a neighbouring sentence.
        clauses = re.split(r"[;；。\n]", quote)
        relevant = [clause for clause in clauses if re.search(r"\brates\b|差[餉饷]", clause)]
        for clause in relevant:
            clause = re.split(r"\brates\b|差[餉饷]", clause, maxsplit=1)[-1]
            clause = re.split(r"management|管理費|管理费", clause, maxsplit=1)[0]
            if re.search(r"quarter|每季|/季|每季度", clause):
                periods.add("quarter")
            if re.search(r"annual|year|每年|/年", clause):
                periods.add("year")
            if re.search(r"month|每月|/月", clause):
                periods.add("month")
    return next(iter(periods)) if len(periods) == 1 else "unknown"


class CostAssessmentService:
    """Build cost assessment from extracted listing fields."""

    def assess(
        self,
        extracted_info: CandidateExtractedInfo,
        max_budget: Optional[int] = None,
        rates_period: str = "month",
    ) -> CostAssessment:
        monthly_rent = parse_monetary_amount(extracted_info.monthly_rent)
        management_fee = parse_monetary_amount(extracted_info.management_fee_amount)
        rates = parse_monetary_amount(extracted_info.rates_amount)
        if rates is not None:
            divisor = {"month": 1, "quarter": 3, "year": 12}.get(rates_period)
            rates = rates / divisor if divisor else None
        deposit_amount = parse_upfront_amount(extracted_info.deposit, monthly_rent) if monthly_rent is not None else None
        agent_fee_amount = parse_upfront_amount(extracted_info.agent_fee, monthly_rent) if monthly_rent is not None else None

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

            known_monthly_cost = round(sum(components), 2)
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
            if deposit_amount is not None:
                components.append(deposit_amount)
            else:
                missing_items.append("deposit")
            if agent_fee_amount is not None:
                components.append(agent_fee_amount)
            else:
                missing_items.append("agent_fee")
            move_in_cost_known_part = sum(components)
            if deposit_amount is not None and agent_fee_amount is not None:
                move_in_cost_confidence = "high"
            elif deposit_amount is not None or agent_fee_amount is not None:
                move_in_cost_confidence = "medium"

        cost_risk_flag = self._determine_risk_flag(
            known_monthly_cost=known_monthly_cost,
            monthly_cost_confidence=monthly_cost_confidence,
            missing_items=missing_items,
            max_budget=max_budget,
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
    ) -> str:
        if (
            max_budget is not None
            and known_monthly_cost is not None
            and known_monthly_cost > max_budget
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
        return "none"

    def _generate_summary(
        self,
        known_monthly_cost: Optional[float],
        cost_risk_flag: str,
        missing_items: List[str],
    ) -> str:
        if known_monthly_cost is None:
            return "The monthly cost cannot be estimated yet. Confirm the rent and extra fees first."

        parts = [f"The known rent and recurring fees total about HKD {known_monthly_cost:,.0f} per month. Utilities and other unlisted expenses may be extra."]
        if cost_risk_flag == "over_budget":
            parts.append("The known cost already exceeds the stated budget.")
        elif cost_risk_flag == "incomplete":
            parts.append("Some cost information has not been stated yet.")
        elif cost_risk_flag == "possible_additional_cost":
            parts.append("There may still be extra charges that have not been confirmed.")

        if missing_items:
            labels = {"monthly_rent": "rent", "management_fee_amount": "management fee amount", "management_fee_included": "whether management fees are included", "rates_amount": "rates amount and billing period", "rates_included": "whether rates are included", "deposit": "deposit", "agent_fee": "agency fee"}
            parts.append("Still to confirm: " + ", ".join(labels.get(item, item.replace("_", " ")) for item in sorted(set(missing_items))[:3]) + ".")
        return " ".join(parts)
