# RentWise assessment quality baseline

`fixtures/assessment_cases.jsonl` contains synthetic, anonymised Hong Kong
rental scenarios. They are not scraped listings and do not represent market
statistics or real users.

The test runs the existing deterministic cost, clause, and candidate
assessment services without LLM, database, map, or network access:

```bash
.venv/bin/python -m pytest -q tests/quality
```

Use this baseline when changing assessment rules. If a case fails, first
decide whether the rule or the expected product behavior is wrong; do not
loosen the fixture just to make CI green.
