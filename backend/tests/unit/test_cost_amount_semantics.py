from types import SimpleNamespace
import pytest
from app.services.cost_assessment_service import CostAssessmentService, parse_upfront_amount, rates_billing_period
from tests.helpers import build_candidate, build_project, build_user


@pytest.mark.parametrize(
    "value,expected",
    [
        ("HKD 36,000", 36000),
        ("$9000", 9000),
        ("9000港元", 9000),
        ("2 months deposit + 1 month advance", 36000),
        ("兩按一上", 36000),
        ("押二付一", 36000),
        ("押一付一", 18000),
        ("押2按1上", 36000),
        ("半佣", 9000),
        ("half-month commission", 9000),
        ("免佣", 0),
        ("no agency fee", 0),
        ("none", 0),
        ("0", 0),
        ("unknown", None),
        ("18000", None),
        ("2-3 months", None),
    ],
)
def test_upfront_amount_never_confuses_currency_and_rent_multiple(value, expected):
    assert parse_upfront_amount(value, 18000) == expected


def test_fixed_deposit_and_free_agency_do_not_multiply_currency_by_rent():
    info = build_candidate(build_project(build_user())).extracted_info
    info.monthly_rent = "18000"
    info.deposit = "HKD 36000"
    info.agent_fee = "免佣"
    result = CostAssessmentService().assess(info)
    assert result.move_in_cost_known_part == 54000
    assert result.move_in_cost_confidence == "high"


@pytest.mark.parametrize("period,expected", [("quarter", 18300), ("year", 18075), ("month", 18900), ("unknown", 18000)])
def test_rates_are_normalized_only_with_a_known_billing_period(period, expected):
    info = build_candidate(build_project(build_user())).extracted_info
    info.monthly_rent = "18000"
    info.management_fee_included = True
    info.rates_amount = "900"
    info.rates_included = False
    result = CostAssessmentService().assess(info, max_budget=18500, rates_period=period)
    assert result.known_monthly_cost == expected
    if period == "unknown":
        assert "rates_amount" in result.monthly_cost_missing_items
    if period == "quarter":
        assert result.cost_risk_flag != "over_budget"


@pytest.mark.parametrize(
    "quote,period",
    [
        ("差餉 $900/季，由租客另付", "quarter"),
        ("Rates 1200/year", "year"),
        ("Rates 300/month", "month"),
        ("Rates 900/quarter or 900/month: please confirm", "unknown"),
        ("Management 1000/month; rates 900", "unknown"),
        ("Management 1000/month, rates 900", "unknown"),
        ("rates 900; management fee 1000/month", "unknown"),
    ],
)
def test_rates_period_cannot_be_borrowed_from_management_fee(quote, period):
    fact = SimpleNamespace(
        field_key="rates_amount", user_action=None, evidence=[SimpleNamespace(quote=quote, claim_kind="explicit")]
    )
    assert rates_billing_period([fact]) == period


def test_old_confirmation_does_not_borrow_period_from_new_evidence():
    fact = SimpleNamespace(
        field_key="rates_amount",
        user_action="confirmed",
        evidence=[SimpleNamespace(quote="rates 900/month", claim_kind="explicit")],
    )
    assert rates_billing_period([fact]) == "unknown"
    fact.user_action = "corrected"
    assert rates_billing_period([fact]) == "month"


@pytest.mark.parametrize("value,expected", [
    ("1/2 month", 9000), ("1 1/2 months", 27000), (".5 months", 9000),
    ("HKD 9k", 9000), ("HK$9,000", 9000), ("USD 9000", None),
    ("US$9000", None), ("HKD -9000", None), ("HKD 8000 to HKD 9000", None),
    ("HKD 8000-HKD 9000", None), ("1/0 month", None), ("-2 months", None),
])
def test_upfront_fraction_currency_and_alternative_boundaries(value, expected):
    assert parse_upfront_amount(value, 18000) == expected


@pytest.mark.parametrize("value,expected", [("18.5k", 18500), ("HKD 18,500", 18500), ("USD 18000", None), ("-18000", None), ("18000-20000", None), ("1e309", None), ("0", 0), ("18,00", None)])
def test_money_parser_does_not_take_the_first_number_from_invalid_amount(value, expected):
    from app.services.cost_assessment_service import parse_monetary_amount
    assert parse_monetary_amount(value) == expected
