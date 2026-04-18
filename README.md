# RentWise

RentWise is a candidate-pool research workspace for Hong Kong renters. You
import listings (text, URLs, screenshots), and the app extracts facts,
scores each candidate against your criteria, estimates real door-to-door
commute times, and explains what to verify next.

This README is the canonical project document. A synchronized Chinese copy
is kept in `README_zh.md`; update both together.

- `backend/` — FastAPI + SQLAlchemy + Alembic
- `frontend/` — Next.js 14 + React + TypeScript + Tailwind
- `legacy/` — archived Streamlit prototype, reference only
- `docs/design-notes.md` — key design decisions and tradeoffs
- `docs/resume-highlights.md` — 4 technical highlights for demos / interviews
- `document/` — source PDFs used by benchmarks

## What RentWise does

**Candidate-pool workflow**
- Auth, search projects with budget, project deletion
- Mixed text + multi-image candidate import; OCR and assessment run as an
  in-process background task
- Dashboard with action-oriented priority queue and a grouped
  investigation checklist
- Candidate detail: decision snapshot, blockers, reassess / shortlist /
  reject, edit with auto-reassessment, delete, on-demand landlord/agent
  outreach draft
- Top-level first-pass recommendation per candidate: shortlist / not
  ready / likely reject

**Compare workflow**
- Manual selection of 2+ shortlisted candidates
- Grouping instead of fake ranking: best current option, viable
  alternatives, not ready for fair comparison, likely drop
- Per-card explanation: why this group, main tradeoff, open blocker,
  next action
- LLM-assisted agent briefing (current take, why now, what could change,
  today's move, confidence note) with deterministic fallback

**Commute evidence** (new)
- Single-destination commute support at the project level
- Candidate location is extraction-first with user correction
- Primary geocoder: HK Gov ALS (free, no key, authoritative for HK in
  English and Chinese)
- Fallback geocoder and all routing: Amap (requires `AMAP_API_KEY`)
- Supports transit / driving / walking
- Geocoder selection runs through a LangGraph LLM tool-use agent —
  it picks between ALS / Amap geocode / Amap POI / MTR-station
  lookup per candidate, subject to a Hong-Kong bounding-box gate
  that rejects mainland coordinates before they reach routing.
  Set `COMMUTE_AGENT_ENABLED=false` to fall back to the deterministic
  resolver.
- Degrades gracefully — commute evidence simply hides when the location
  or destination can't be resolved; never blocks the rest of the app

**UI**
- Every user-facing page (landing, login, projects list, dashboard,
  candidate detail, compare) shares one visual system: Sparkles branded
  header, gradient backdrop, inline Button / Badge / Card primitives,
  Tailwind-only, no shadcn runtime.

## Repository layout

```text
RentWise/
  backend/
    app/
      api/v1/              # auth, projects, candidates, dashboard, comparison, investigation
      core/                # config
      db/                  # models, session
      services/            # extraction, assessment, compare, OCR, commute, ...
      integrations/        # als, amap, llm
      data/                # versioned benchmark data
    alembic/               # migrations
    tests/
  frontend/
    app/                   # Next.js app router pages
    lib/                   # api client, types, auth helpers
  docs/
    design-notes.md        # key design decisions and tradeoffs
    resume-highlights.md   # 4 technical highlights for demos / interviews
  document/                # source PDFs
  legacy/                  # archived prototype
```

### Backend modules

- `app/main.py` — FastAPI entry point, startup hooks (OCR prewarm)
- `app/core/config.py` — env-driven settings; secrets only from `.env`
- `app/db/models.py` — users, projects, candidates, assessments, source assets
- `app/api/v1/*.py` — auth, projects, candidates, dashboard, comparison, investigation
- `app/services/extraction_service.py` — LLM-driven structured extraction
- `app/services/cost_assessment_service.py` — budget fit + confidence
- `app/services/clause_assessment_service.py` — lease, repairs, move-in
- `app/services/candidate_assessment_service.py` — overall recommendation
- `app/services/candidate_pipeline_service.py` — orchestrates extraction + assessments
- `app/services/candidate_import_service.py` + `candidate_import_background_service.py` — import entry + background worker
- `app/services/ocr_service.py` — OCR provider abstraction (rapidocr / paddleocr / mistral)
- `app/services/file_storage_service.py` — upload storage abstraction
- `app/services/dashboard_service.py` + `priority_service.py` + `investigation_service.py` — dashboard assembly
- `app/services/comparison_service.py` + `comparison_briefing_service.py` — compare grouping + LLM briefing
- `app/services/benchmark_service.py` — SDU median-rent benchmark lookup
- `app/services/commute_service.py` — geocode candidate + destination, then route
- `app/services/candidate_contact_plan_service.py` — outreach draft
- `app/services/tenancy_rag_service.py` — BM25 + jieba retriever over the HK
  tenancy ordinance guide; backs clause-assessment legal citations
- `app/agent/commute_resolver_agent.py` — LangGraph tool-use agent that
  picks between ALS / Amap geocode / Amap POI to resolve candidate coordinates
- `app/agent/tools/commute_tools.py` — tool schemas + executors + HK-bbox gate
- `app/integrations/als/client.py` — HK Gov Address Lookup Service client
- `app/integrations/amap/client.py` — Amap geocode / POI / route client

### Frontend pages

- `app/page.tsx` — landing
- `app/login/page.tsx` — login / register
- `app/projects/page.tsx` — project list + create
- `app/projects/[id]/page.tsx` — dashboard, priority queue, investigation checklist
- `app/projects/[id]/import/page.tsx` — mixed text + image import
- `app/projects/[id]/candidates/[candidateId]/page.tsx` — candidate detail
- `app/projects/[id]/compare/page.tsx` — compare workspace + briefing
- `lib/api.ts` / `lib/types.ts` / `lib/auth.ts`

## Setup

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API at `http://localhost:8000`, Swagger at `/docs`.

OCR defaults to `rapidocr_onnxruntime` (light, Windows-friendly). For
memory-constrained hosts (e.g. Render free 512MB), set
`OCR_PROVIDER=mistral` with `MISTRAL_API_KEY`. Paddle remains an
opt-in alternative; install `paddleocr` and `paddlepaddle` yourself if you
switch.

If your local Postgres was created by the old startup `create_all()` path,
run `alembic stamp head` once before switching to normal `alembic upgrade
head` flow.

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Frontend at `http://localhost:3000`.

## Environment variables

### Backend (required)

- `SECRET_KEY`
- `DATABASE_URL` — prefer `postgresql+asyncpg://...?ssl=require`. Common
  `postgres://` and `postgresql://` URLs are auto-normalized to asyncpg.
- `LLM_PROVIDER` — `groq` or `ollama`

### Backend (optional)

- `GROQ_API_KEY`, `GROQ_MODEL`
- `OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_MODEL`
- `BACKEND_CORS_ORIGINS` — comma-separated origins
- `AMAP_API_KEY` — enables commute routing; without it, commute evidence
  reports "Map service not configured" and the rest of the app works normally
- `FILE_STORAGE_PROVIDER`, `LOCAL_UPLOAD_ROOT`
- `OCR_PROVIDER` (`rapidocr` | `paddleocr` | `mistral` | `ocr_space`)
- `MISTRAL_API_KEY` (required when `OCR_PROVIDER=mistral`), `MISTRAL_OCR_MODEL`
- `OCR_MAX_IMAGE_DIMENSION`, `OCR_PREWARM_ON_STARTUP`, `LOW_MEMORY_MODE`
- `PADDLEOCR_LANG`, `OCR_USE_DOC_ORIENTATION`, `OCR_USE_DOC_UNWARPING`,
  `OCR_USE_TEXTLINE_ORIENTATION`, `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`

The HK Gov ALS geocoder requires no key and no configuration.

### Frontend

- `NEXT_PUBLIC_API_URL` — raw backend URL only, e.g.
  `https://rentwise-api.onrender.com`. Do not paste
  `NEXT_PUBLIC_API_URL=...` into Vercel's value field.

## Deployment

Recommended hosted setup:

1. **Frontend** — Vercel, project root `frontend/`
2. **Backend** — Render Python web service, root `backend/`, pin Python
   runtime to 3.11 (the repo ships `.python-version` = `3.11.11`; if Render
   ignores it, add `PYTHON_VERSION=3.11.11` as env var)
3. **Database** — Neon, asyncpg connection string
4. `NEXT_PUBLIC_API_URL` in Vercel → Render backend URL
5. `BACKEND_CORS_ORIGINS` on Render → your Vercel production (and preview)
   domains

Render start command:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Cloud env essentials (Render):

- `APP_ENV=production`
- `DATABASE_URL=postgresql+asyncpg://<user>:<pw>@<host>/<db>?ssl=require`
- `SECRET_KEY=<strong-random-secret>`
- `LLM_PROVIDER=groq` + `GROQ_API_KEY=<...>`
- `AMAP_API_KEY=<...>` for commute
- Free 512MB tier: `OCR_PROVIDER=mistral` + `MISTRAL_API_KEY`,
  `OCR_PREWARM_ON_STARTUP=false`, `LOW_MEMORY_MODE=true`
- Larger instances: `OCR_PROVIDER=rapidocr`

Storage caveat: the local storage adapter is fine for short demos but
Render's filesystem is ephemeral. Move candidate uploads to object
storage before treating a deployment as production-ready.

## Testing

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

Real Postgres integration flow:

```bash
cd backend
set RUN_DB_INTEGRATION=1
.\venv\Scripts\python.exe -m unittest tests.integration.test_db_flow
```

The suite covers priority ranking, investigation checklist, candidate
recommendation, compare grouping + explanation + briefing fallback, OCR
parsing, and benchmark lookup.

A separate pytest-marked eval suite under `backend/tests/evals/` guards
against regressions in the LLM pipeline: golden listings for extraction,
golden commute scenarios for the resolver agent, and a BM25-only recall
test for the tenancy index. Gated behind `pytest.mark.eval` and skipped
by default:

```bash
cd backend
GROQ_API_KEY=... AMAP_API_KEY=... pytest -m eval -q
```

Structured JSON reports are written to `backend/tests/evals/reports/`
so quality drift can be diffed commit-to-commit. See
`backend/tests/evals/README.md` for the fixture / floor details.

## Data safety checklist

Before pushing to GitHub:

- `backend/.env`, `frontend/.env.local`, any root `.env` are git-ignored
- `backend/storage/` is git-ignored
- No model caches, logs, venvs, or build artifacts committed
- Rotate any credential ever pasted into chat, terminal, or screenshots
- `.env.example` contains only placeholders
- Review `git status` before every push

## Evidence layers

RentWise uses three independent evidence layers. None of them feed the
main candidate score directly — they exist to support user judgment.

**1. SDU benchmark** (active)
- Source: `document/SDU_median_rents.pdf`, extracted into
  `backend/app/data/benchmark_sdu_rents.json`
- Shown on candidate detail and compare only when the candidate is
  likely an SDU and has a district. Always carries an explicit
  "subdivided units, general reference only" disclaimer.

**2. Commute** (active)
- Project-level configuration: enabled flag, destination label,
  destination query, mode (transit/driving/walking), max minutes
- Candidate-level location: address, building name, nearest station,
  district, location confidence
- Resolution ladder: HK Gov ALS → Amap /geocode → Amap POI search
- Routing: Amap transit / driving / walking
- Surfaces "Location not precise enough" with the actual confidence
  note when all geocoders fail, instead of hiding the reason.

**3. Tenancy guide RAG** (active)
- Source: `document/AGuideToTenancy_ch.pdf` (CID-encoded scan) rendered
  page-by-page via PyMuPDF and OCR'd with `rapidocr_onnxruntime`,
  chunked at ~400 characters, tokenized with jieba, indexed with
  BM25Okapi. Index is committed at `backend/app/data/tenancy_index.json`
  (22 chunks); rebuild with `python -m scripts.build_tenancy_index`.
- Retrieval runs only when a candidate's `clause_risk_flag != "none"`.
  Pipeline: BM25 top-5 → LLM rerank to top-2 (raw BM25 top-2 fallback
  if the LLM call fails).
- Output attaches to `ClauseAssessment.legal_references` (JSONB column,
  migration `20260418_0008`). The frontend surfaces it as an
  "Ordinance reference" card on the candidate detail page.
- No embeddings, no external API: keyword-dense legal Chinese is well
  suited to BM25, and staying local sidesteps the retired course Ollama
  endpoint.

## Phase status

- **Phase 1** (auth, projects, candidate import, dashboard, detail,
  editing, deletion, budget, migrations, tests) — complete
- **Phase 2** (compare MVP with grouping + briefing) — complete
- **Phase 2.5** (agent-style explanation, decision signals) — active
- **Phase 3** (commute evidence + cohesive UI redesign) — complete

## Product philosophy

Two truths that drive the current direction:

1. More analysis output does not automatically produce better decisions.
   The product is strongest when the user can see what to do next within
   seconds.
2. External evidence should support trust, not create fake precision.
   Benchmark stays scoped. Commute is support evidence, never a hidden
   scoring input. Tenancy RAG quotes the ordinance verbatim with page
   citations rather than paraphrasing — the source is the argument.
