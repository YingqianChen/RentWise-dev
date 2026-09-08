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


def test_matching_does_not_accept_opposite_meanings_or_partial_numbers():
    from tests.evals.scoring import fuzzy_field_match
    for expected, actual in [('furnished', 'unfurnished'), ('furnished', 'not furnished'), ('1800', '18000'), ('included', 'not included'), (True, 'true'), (False, 'false')]:
        assert not fuzzy_field_match(expected, actual), (expected, actual)
    assert fuzzy_field_match(['28500'], 'HKD 28,500')
    assert fuzzy_field_match(['no agency fee', 'none', '0'], 'none')
    assert fuzzy_field_match(None, 'unknown')
    assert not fuzzy_field_match(None, False)


def test_incomplete_eval_is_not_reported_as_model_accuracy():
    from scripts.report_extraction_eval import summarize
    report = summarize({'total_cases': 20, 'case_error_count': 17, 'overall_pass_rate': 0.149, 'failed_cases': []})
    assert report['completed_cases'] == 3
    assert report['evaluation_complete'] is False
    assert 'not a model accuracy' in report['interpretation']


def test_unattempted_cases_are_separate_from_failed_requests():
    from scripts.report_extraction_eval import summarize
    report = aggregate_report([
        CaseResult('failed', [FieldResult('rates_included', False, True, None)], error='llm_unavailable'),
        CaseResult('not_run', [FieldResult('rates_included', False, True, None)], error='not_run_service_unavailable', attempted=False),
    ])
    summary = summarize(report)
    assert summary['attempted_cases'] == 1
    assert summary['not_run_cases'] == 1
    assert summary['service_or_processing_errors'] == 1
    assert summary['evaluation_complete'] is False


async def test_eval_stops_calling_provider_after_repeated_unavailability(monkeypatch):
    import importlib
    from unittest.mock import AsyncMock
    import pytest
    from app.services.analysis_errors import analysis_error
    monkeypatch.setenv('GROQ_API_KEY', 'offline-test-placeholder')
    module = importlib.import_module('tests.evals.test_extraction_eval')
    extract = AsyncMock(side_effect=analysis_error('llm_unavailable', retryable=True))
    monkeypatch.setattr(module.ExtractionService, 'extract', extract)
    saved = {}
    def writer(_name, report):
        saved.update(report)
    samples = [{'id': str(i), 'raw_listing_text': 'Rates included.', 'expected': {'rates_included': True}} for i in range(5)]
    with pytest.raises(AssertionError):
        await module.test_extraction_golden_set(samples, writer)
    assert extract.await_count == 2
    assert saved['attempted_cases'] == 2
    assert saved['not_run_cases'] == 3
