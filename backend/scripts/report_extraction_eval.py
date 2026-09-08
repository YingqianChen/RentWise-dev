"""Summarize a saved eval without confusing service failures with model accuracy.

No network or model calls. Run: python -m scripts.report_extraction_eval
"""
import json
from pathlib import Path


def summarize(report: dict) -> dict:
    total = report['total_cases']
    errors = report.get('case_error_count', 0)
    return {
        'attempted_cases': report.get('attempted_cases', total),
        'not_run_cases': report.get('not_run_cases', 0),
        'completed_cases': total - errors,
        'service_or_processing_errors': errors - report.get('not_run_cases', 0),
        'evaluation_complete': errors == 0,
        'overall_field_pass_rate': report['overall_pass_rate'],
        'interpretation': (
            'Incomplete run: this is not a model accuracy measurement.' if errors
            else 'Synthetic fixture score only; not a real-user accuracy estimate.'
        ),
        'failed_cases': report['failed_cases'],
    }


if __name__ == '__main__':
    source = Path(__file__).parents[1] / 'tests/evals/reports/extraction_last_run.json'
    print(json.dumps(summarize(json.loads(source.read_text())), ensure_ascii=False, indent=2))
