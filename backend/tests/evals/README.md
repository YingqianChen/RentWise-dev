# RentWise eval suite

End-to-end quality regression harness. Runs against real LLM + geocoding
calls, so it's gated behind `pytest.mark.eval` and **skipped by default** —
the fast unit/integration suites don't depend on it.

## Run

```bash
cd backend
GROQ_API_KEY=sk-... AMAP_API_KEY=... pytest -m eval -q
```

Without `GROQ_API_KEY`, every eval is skipped (not failed). Commute evals
additionally need `AMAP_API_KEY`.

## Layout

- `fixtures/golden_listings.jsonl` — raw HK listing text + expected extracted
  fields. Expected values may be strings or lists (any-of accept).
- `fixtures/golden_listings_review.json` — review status and coverage map for
  the synthetic, anonymised listing samples. This records sample review, not
  real-model accuracy.
- `fixtures/golden_commutes.jsonl` — candidate location signals + expected
  origin station / mode / minute range.
- `scoring.py` — `fuzzy_field_match`, `numeric_in_range`, `aggregate_report`.
- `test_extraction_eval.py` — runs `ExtractionService.extract()` over the
  listing fixtures, scores each extracted field, asserts pass-rate floors.
- `test_commute_agent_eval.py` — runs `CommuteResolverAgent.ainvoke()` on the
  commute fixtures, routes with Amap, asserts origin-station / mode / minute
  accuracy.
- `test_tenancy_rag_eval.py` — retrieval-recall check for the BM25 index over
  `document/AGuideToTenancy_ch.pdf`. No LLM calls; runs even without
  `GROQ_API_KEY` whenever `-m eval` is passed. Skips if the committed
  `app/data/tenancy_index.json` is missing (rebuild with
  `python -m scripts.build_tenancy_index`).
- `reports/` — written on every run; one JSON per test file. Diff across
  commits to see quality drift.

## Adding samples

Each fixture line is a single JSON object (blank lines + lines starting `#`
are ignored).

**Listings:** minimum required keys are `id`, `raw_listing_text`, `expected`.
Expected values may be a string (exact fuzzy match) or a list of acceptable
synonyms. Booleans are compared literally.

**Commutes:** `id`, `candidate_facts` (dict matching the agent's
`address_text` / `building_name` / `nearest_station` / `district` signals),
`project_destination` (any HK query that geocodes), `mode`, and `expected`
with some subset of `origin_station_any_of`, `mode_any_of`, `minutes_range`.

Anonymise real data: strip phone numbers and the first part of street
numbers. Fixtures are committed — treat them like test code.

The listing set currently has 20 synthetic samples. Six newer samples cover
Cantonese/English mixed wording, separate fees, quarterly rates, subdivided or
shared-bathroom units, tong lau repair wording, serviced apartments, and
conflicting fee sources. The default quality test checks the fixture contract;
the real LLM extraction eval remains optional and still requires
`GROQ_API_KEY`.

## Thresholds

See `_FLOORS` / `_OVERALL_FLOOR` in each test. Start generous; tighten as
quality improves. A failing floor means a real regression — don't loosen it
without understanding why.

Rationale for current floors:

- Extraction: rent + district are must-haves and get 0.70 floors. Deposit
  and lease term are noisier in real listings (multiple formats), 0.50
  floor.
- Commute: mode accuracy should be near-perfect once agent + bbox fix land
  (0.70). Origin station and minutes are more variable (ALS scoring can
  drift by a station or two) — 0.50 floors.
- Tenancy RAG: top-3 recall against expected page ranges — 0.60 floor.
  Low ceiling because the source PDF is scanned; OCR sometimes emits
  garbled glyphs that knock out otherwise-relevant chunks.

## 2026-09-09 quality review

Six additional rates-responsibility cases cover landlord payment, tenant payment,
utilities without rates, ambiguous all-inclusive wording, named inclusion and
conflicting claims. Null expectations deliberately mean unknown/conflicted.
These six samples were checked by the coding assistant; independent human review
is still needed. The fixture metadata records that distinction.

The matcher now requires a normalized full value or an explicit acceptable
variant. It does not accept substrings (`furnished` / `unfurnished`, `1800` /
`18000`). Booleans must be booleans. This breaks comparability with old scores.
Full source wording in deposit, lease and station fields may require additional
human-checked aliases; do not loosen matching just to turn a run green.

Rates inclusion now has a 0.90 release floor and the overall floor is 0.80.
These are targets, not claimed results. A run with any service errors fails even
when its successful examples score well. Use
`python -m scripts.report_extraction_eval` to summarize a saved result offline.

The 2026-09-09 live run made 20 requests with SDK retries disabled: 3 completed,
17 returned `llm_unavailable`. No further requests were made. The run is
incomplete and does not establish model accuracy or prove the new prompt.
The later local amount/fee evidence guards have not been re-evaluated live.
Future runs should be paced to the account's provider limits, log safe HTTP
status categories, and use a bounded request allowance. The harness now stops sending new
requests after two consecutive service-unavailable results; untouched samples
are recorded as not run, and the batch still fails. Never print keys or provider exception bodies.
