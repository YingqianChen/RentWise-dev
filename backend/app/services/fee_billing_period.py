"""Billing units belong to each fee and freeze with user confirmation."""

import re

FEE_AMOUNT_FIELDS = {"rates_amount", "management_fee_amount"}
BILLING_PERIODS = {"month", "quarter", "year", "unknown"}
_FEE_NAMES = {
    "rates_amount": r"\brates\b|差[餉饷]",
    "management_fee_amount": r"\bmanagement(?:\s+fees?)?\b|管理[費费]",
}
_OTHER_COSTS = r"\brent\b|租金|月租|\butilities\b|水[費费]|電[費费]"


def system_billing_period(fact) -> str:
    if fact.field_key not in FEE_AMOUNT_FIELDS:
        return "unknown"
    own_name = _FEE_NAMES[fact.field_key]
    other_names = "|".join(pattern for key, pattern in _FEE_NAMES.items() if key != fact.field_key) + "|" + _OTHER_COSTS
    periods = set()
    for claim in fact.evidence:
        if claim.claim_kind != "explicit":
            continue
        # Split clauses but keep commas within currency amounts (e.g. 1,200).
        for clause in re.split(r"[;；。\n]|(?<!\d)[,，]|[,，](?!\d)", claim.quote.lower()):
            match = re.search(own_name, clause)
            if match is None:
                continue
            prefix = clause[: match.start()]
            if re.search(other_names, prefix):
                prefix = ""
            suffix = re.split(other_names, clause[match.end() :], maxsplit=1)[0]
            segment = prefix + " " + suffix
            if re.search(r"quarter|每季|/季", segment):
                periods.add("quarter")
            if re.search(r"annual|year|每年|/年", segment):
                periods.add("year")
            if re.search(r"month|每月|/月", segment):
                periods.add("month")
    return next(iter(periods)) if len(periods) == 1 else "unknown"


def fee_billing_period(facts, field_key: str) -> str:
    fact = next((item for item in facts if item.field_key == field_key), None)
    if fact is None:
        return "unknown"
    if fact.user_action in {"corrected", "confirmed"}:
        saved = getattr(fact, "user_billing_period", None)
        if saved in BILLING_PERIODS:
            return saved
        # Compatibility: older correction inputs explicitly meant monthly HKD;
        # older confirmations did not capture a unit and remain unknown.
        return "month" if fact.user_action == "corrected" else "unknown"
    if fact.user_action is not None:
        return "unknown"
    return system_billing_period(fact)
