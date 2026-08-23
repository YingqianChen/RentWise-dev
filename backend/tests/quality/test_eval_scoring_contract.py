"""Contract checks for complete reporting when one eval case errors."""

from tests.evals.scoring import CaseResult, FieldResult, aggregate_report


def test_aggregate_report_keeps_case_error_visible() -> None:
    report = aggregate_report(
        [
            CaseResult(
                case_id="broken_case",
                fields=[FieldResult("monthly_rent", False, ["18000"], None)],
                error="invalid_model_output",
            )
        ]
    )

    assert report["case_error_count"] == 1
    assert report["failed_cases"] == [
        {
            "case_id": "broken_case",
            "failures": [
                {"field": "monthly_rent", "expected": ["18000"], "actual": None}
            ],
            "error": "invalid_model_output",
        }
    ]
