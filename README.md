# RentWise

This README is the **canonical project document** for the active codebase.

If older notes, specs, or refactor docs disagree with this file, treat this README as the current source of truth. A synchronized Chinese review copy is kept in `README_zh.md`; both documents should be updated together.

RentWise is being rebuilt from a Streamlit prototype into a monorepo with:

- `backend/`: FastAPI + SQLAlchemy + LangGraph
- `frontend/`: Next.js + React + TypeScript
- `legacy/`: archived Streamlit prototype code for reference only

## Current Product Scope

The rebuilt app now covers Phase 1 stabilization plus an initial Phase 2 compare workflow.

### Candidate-pool workflow

The active product focuses on a candidate-pool decision workflow:

- user registration and login
- search project creation
- search project budget editing
- search project deletion
- mixed text + multi-image candidate import
- background OCR / extraction / assessment after import
- dashboard summary with action-oriented priority candidates and investigation items
- dashboard investigation checklist now groups shared blockers instead of repeating the same prompt for each listing
- candidate detail view with reassess / shortlist / reject actions
- candidate detail outreach drafting for the next landlord / agent message
- candidate deletion with confirmation
- candidate editing with automatic reassessment
- candidate detail now keeps the main surface focused on the decision snapshot and blockers, while benchmark, OCR evidence, and supporting details stay secondary until needed
- dashboard now shows background-processing candidates as processing work instead of rendering them like empty assessed candidates
- dashboard now supports candidate deletion directly from the candidate list
- budget edits now trigger budget-dependent reassessment for existing completed candidates
- top-level first-pass recommendation:
  - shortlist recommendation
  - not ready
  - likely reject

### Compare workflow

The current compare experience is designed as a shortlist decision workspace rather than a field table:

- manual candidate selection from the dashboard
- compare workspace for 2 or more selected candidates
- decision grouping instead of fake exact ranking:
  - best current option
  - viable alternatives
  - not ready for fair comparison
  - likely drop
- explanation-rich compare cards with:
  - why the candidate is in its group
  - main tradeoff
  - open blocker
  - next action
- recommended next actions for the compare set:
  - who to contact first
  - what to ask next
  - who is ready for viewing
  - who can be deprioritized
- suggested compare preview on the dashboard
- compare context on the candidate detail page so the decision story stays consistent across surfaces
- LLM-assisted agent briefing on the compare page, focused on:
  - current take
  - why now
  - what could change
  - today's move
  - confidence note
- compare page now keeps supporting differences shorter so the main decision flow stays on briefing, groups, and next actions

Not in the current scope:

- RAG-driven district workflow
- commute calculation
- saved compare history
- map-backed commute support

## What The Product Is Trying To Be

RentWise is not meant to be a field extractor or a generic chat assistant.

The current product direction is:

- a candidate-pool decision workspace
- a compare-driven shortlist tool
- an agent-assisted explanation layer

The intended user value is:

- help users decide which listings deserve attention
- make uncertainty visible instead of hiding it
- explain tradeoffs in plain language
- turn "I have several options and do not know what to do next" into an actionable workflow

## Repository Layout

```text
RentWise/
  backend/
  frontend/
  legacy/
  docs/
```

Key directories:

- `backend/`: API, database models, OCR pipeline, assessment services, Alembic migrations, tests
- `frontend/`: Next.js app routes, API client, auth helpers, candidate/project pages
- `docs/`: design notes, presentation notes, roadmap material
- `legacy/`: archived prototype artifacts kept for reference only

## Key Modules And Files

### Backend

- `backend/app/main.py`
  - FastAPI entry point and startup hooks, including OCR prewarm
- `backend/app/core/config.py`
  - environment-driven settings; secrets now come only from `.env` or the process environment
- `backend/app/db/models.py`
  - SQLAlchemy models for users, projects, candidates, assessments, and source assets
- `backend/app/api/v1/auth.py`
  - registration and login routes
- `backend/app/api/v1/projects.py`
  - project create/update/delete logic, including budget updates
- `backend/app/api/v1/candidates.py`
  - candidate import, list/detail, edit, delete, reassessment
- `backend/app/api/v1/dashboard.py`
  - dashboard response assembly for project-level decision views
- `backend/app/api/v1/comparison.py`
  - compare workflow routes
- `backend/app/services/candidate_import_background_service.py`
  - in-process background OCR and assessment pipeline
- `backend/app/services/ocr_service.py`
  - OCR provider abstraction, result normalization, and backend selection
- `backend/app/services/file_storage_service.py`
  - upload storage abstraction; local development currently writes to `backend/storage/`
- `backend/app/services/extraction_service.py`
  - LLM-driven structured extraction from combined candidate text
- `backend/app/services/cost_assessment_service.py`
  - cost-focused heuristics and confidence outputs
- `backend/app/services/clause_assessment_service.py`
  - lease / repair / move-in semantic assessment
- `backend/app/services/candidate_assessment_service.py`
  - overall candidate recommendation, completeness, and next action
- `backend/app/services/comparison_service.py`
  - shortlist grouping and compare explanations
- `backend/app/services/comparison_briefing_service.py`
  - compare-page LLM briefing with fallback behavior
- `backend/app/services/benchmark_service.py`
  - SDU benchmark evidence lookup using local structured data
- `backend/app/data/benchmark_sdu_rents.json`
  - versioned SDU median-rent benchmark data file
- `backend/alembic/`
  - schema migration history
- `backend/tests/`
  - unit and integration coverage for major flows

### Frontend

- `frontend/app/page.tsx`
  - landing page
- `frontend/app/login/page.tsx`
  - login view
- `frontend/app/projects/page.tsx`
  - project list view
- `frontend/app/projects/[id]/page.tsx`
  - project dashboard, candidate queue, budget editing
- `frontend/app/projects/[id]/import/page.tsx`
  - mixed text + image import form with processing state UX
- `frontend/app/projects/[id]/candidates/[candidateId]/page.tsx`
  - candidate detail, reassessment, OCR evidence, delete action
- `frontend/app/projects/[id]/compare/page.tsx`
  - compare workspace and LLM briefing
- `frontend/lib/api.ts`
  - browser API client and response/error handling
- `frontend/lib/types.ts`
  - shared frontend response types
- `frontend/lib/auth.ts`
  - token storage helpers

## Backend Setup

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

If you want image OCR during candidate import, the default backend now uses `rapidocr_onnxruntime`, which is lighter for Windows + CPU local development and better aligned with screenshot-heavy import flows. If you explicitly switch `OCR_PROVIDER=paddleocr`, install `paddleocr` and `paddlepaddle` manually in `backend\\venv` before starting the API.

If your local PostgreSQL database was created by the earlier startup `create_all()` flow, run this one-time command instead before switching to Alembic-managed migrations:

```bash
alembic stamp head
```

Then continue to use:

```bash
alembic upgrade head
```

`stamp head` only aligns Alembic's recorded revision. It does not add missing tables or columns.

Backend API:

- `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Frontend Setup

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Frontend:

- `http://localhost:3000`

## Environment Variables

### Backend

Required:

- `SECRET_KEY`
- `DATABASE_URL`
- `LLM_PROVIDER`

Optional provider settings:

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `OLLAMA_HOST`
- `OLLAMA_API_KEY`
- `OLLAMA_MODEL`
- `FILE_STORAGE_PROVIDER`
- `LOCAL_UPLOAD_ROOT`
- `OCR_PROVIDER`
- `PADDLEOCR_LANG`
- `OCR_USE_DOC_ORIENTATION`
- `OCR_USE_DOC_UNWARPING`
- `OCR_USE_TEXTLINE_ORIENTATION`
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`
- `OCR_PREWARM_ON_STARTUP`
- `OCR_MAX_IMAGE_DIMENSION`

Notes:

- The rebuilt backend currently targets PostgreSQL.
- SQLite is not a supported runtime for the current schema.
- API keys are no longer hardcoded in `backend/app/core/config.py`; provider secrets must come from `backend/.env` or the process environment.
- For Neon, use an `asyncpg` SQLAlchemy URL such as `postgresql+asyncpg://...?...ssl=require`.

### Frontend

- `NEXT_PUBLIC_API_URL`

Default:

- `http://localhost:8000`

## Deployment Notes

Current deployment assumptions:

- database: PostgreSQL, including hosted services such as Neon
- backend: FastAPI process with an in-process background worker
- frontend: Next.js app
- OCR runtime: RapidOCR on ONNX Runtime by default, with optional PaddleOCR fallback

Important production caveats:

- Candidate OCR and assessment currently run in an in-process background worker, not an external job queue.
- Local file storage is suitable for development only. The upload layer is abstracted, but production deployment should move to object storage rather than relying on the backend filesystem.
- OCR still does real image work on CPU, but the default path now favors lower startup cost and better Windows-local responsiveness. The codebase still prewarms the OCR engine and downscales large images before OCR, and PaddleOCR remains available only as an explicit fallback when you need to trade more latency for different recognition behavior.

Recommended production direction:

1. PostgreSQL on Neon or another managed provider
2. dedicated object storage for uploaded screenshots
3. backend deployment with persistent environment variables
4. frontend deployment on a Next.js-compatible host
5. future upgrade from in-process background work to an external queue if import volume grows

## Release And Data-Safety Checklist

Before pushing to GitHub:

- confirm `backend/.env`, `frontend/.env.local`, and any root `.env` files are ignored and not tracked
- confirm `backend/storage/` is ignored
- do not commit model caches, logs, virtual environments, or build artifacts
- do not commit exported course/reference HTML files or ad hoc local scratch files
- rotate any credentials that were ever pasted into chat, docs, screenshots, or terminals
- keep only placeholder values in `.env.example`
- review `git status` before every push

Sensitive local files that must stay out of git:

- `backend/.env`
- `frontend/.env.local`
- `backend/storage/`
- `frontend/node_modules/`
- `frontend/.next/`
- local logs, caches, and generated artifacts

## Product Notes

- `legacy/streamlit_app/` is not the active product entry point.
- Database schema is managed with Alembic.
- Run `alembic upgrade head` before starting the backend on a fresh environment.
- If you already had tables from the older startup-created schema, run `alembic stamp head` once to align Alembic with the existing database, then keep using `alembic upgrade head` for every later schema change.
- If you see errors like `column candidate_extracted_info.suspected_sdu does not exist`, your code is ahead of your local database schema. Run `alembic upgrade head` in `backend/`.
- Project deletion removes related candidates, assessments, and investigation items through database cascade rules.
- Candidate editing is currently available from the candidate detail page.
- Compare results are generated on demand and are not persisted yet.
- Dashboard can surface a suggested compare set based on the current shortlist shape.
- Candidate detail can open a compare workspace centered on the current candidate.
- Compare page includes an LLM-assisted briefing layer with deterministic fallback if the model call fails.
- Candidate detail pushes structured fields and source text into supporting sections so the decision read comes first.
- Dashboard treats open questions as a grouped investigation checklist rather than a repeated per-listing warning feed.
- Frontend API error handling keeps real backend response errors separate from true network failures, so candidate edit/save surfaces more actionable messages.
- Repair responsibility assessment now uses an LLM-normalized repair note plus conservative rule-based semantics, so signals like agency-supported repairs are treated as positive but still unconfirmed instead of being collapsed into a generic unknown.
- Lease term and move-in timing now follow the same pattern: the LLM first normalizes the clause text, then conservative semantic rules decide whether the signal looks standard, rigid, unstable, fit, uncertain, or mismatched.
- Candidate detail now translates internal clause states into user-facing explanations instead of exposing raw labels like `rigid` or `uncertain` directly.
- Candidate import supports mixed text + multi-image input in one form. Uploaded screenshots are stored through a storage abstraction that currently uses a local development adapter, then OCR text is merged back into the normal `combined_text` analysis pipeline.
- Development uploads are stored under `backend/storage/`, which must stay out of git.
- OCR import stores uploaded source-asset metadata separately from extracted candidate fields so the async candidate pipeline can reuse OCR evidence without triggering lazy-load issues during import.
- If image-only import creates empty extraction results, first verify that the configured OCR runtime is installed inside `backend\\venv`. The default setup expects `rapidocr_onnxruntime`; the Paddle fallback additionally needs both `paddleocr` and `paddlepaddle`. Background import failures are now written back onto the candidate so the detail page can show the real OCR failure reason instead of a fake network-style error.
- Candidate import is processed by an in-app background task instead of blocking the request until OCR and assessment finish. The import page returns quickly, redirects to the candidate detail page, and the detail page polls until the background stages finish.
- The initial queued import response returns a placeholder candidate state without forcing lazy assessment loads, so image import no longer crashes at response serialization time before the background worker starts.
- The project dashboard also polls while any candidate is still processing, so finished OCR jobs can move into the priority queue without forcing a manual refresh.
- Candidates that are still processing are shown as explicit background work on the dashboard instead of appearing as blank low-information cards, and they are temporarily excluded from compare selection until assessment finishes.
- OCR startup is prewarmed by default so the first user import does not have to pay the full model boot cost inside the request path, regardless of which supported OCR provider you choose.
- Uploaded screenshots are resized down to a configurable maximum dimension before OCR, which significantly reduces CPU-bound latency on oversized mobile screenshots without changing the mixed text + image workflow.
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` remains available for the optional Paddle fallback and is pushed into `os.environ` before `paddleocr` is imported, so setting it in `backend/.env` suppresses the model-hoster connectivity check without requiring a manual terminal export.
- Candidate processing stages are currently:
  - `queued`
  - `running_ocr`
  - `extracting`
  - `completed`
  - `failed`
- This is intentionally an in-process background worker, not an external queue. It improves perceived speed immediately, but tasks are still tied to the running backend process.
- Candidate detail supports permanent deletion with a confirmation step, and the project workspace supports inline budget updates.
- Candidate deletion is available both from candidate detail and directly from the dashboard candidate list.
- Updating a project's budget refreshes budget-dependent assessments for existing completed candidates, so the dashboard and candidate recommendations stay aligned with the new cap.
- Candidate detail exposes OCR evidence per uploaded file so you can inspect what text OCR actually read before blaming downstream extraction.
- Candidate detail now includes an on-demand LLM outreach draft that turns the current blockers into 2 to 3 concrete landlord / agent questions plus a short English message draft. It is intentionally generated only when requested so the page does not become noisier for users comparing only a few listings.
- Candidate detail now follows a lighter decision-workspace pattern: the main screen stays focused on the live decision, while benchmark notes and deeper evidence panels are collapsed by default.
- The import page uses a custom upload trigger instead of the browser's native file-button label, which avoids mixed-language UI inside an otherwise English interface.

## UX Reality Check

One of the biggest current product risks is information overload.

The codebase can already generate:

- structured extraction
- cost assessment
- clause assessment
- candidate assessment
- compare grouping
- compare explanation
- next-step guidance

That is useful, but it also creates a risk:

- too much structured output
- too many repeated explanations
- too many page sections competing for attention

The current direction is therefore:

- keep the decision path visible
- push supporting detail lower on the page
- reduce duplicate explanation across sections
- use explanation to support decisions, not to bury them

## Phase Status

### Phase 1

Phase 1 is effectively complete:

- auth
- projects
- candidate import and reassessment
- dashboard
- candidate detail
- project deletion
- candidate editing
- candidate deletion
- project budget editing
- Alembic migrations
- test coverage for the main backend flows

### Phase 2

Phase 2 compare MVP is active:

- manual compare-set selection
- grouped shortlist comparison
- compare explanation and tradeoff output
- compare context from dashboard and candidate detail
- LLM-assisted compare briefing

### Phase 2.5

Phase 2.5 is partially active:

- compare page already has an agent-style briefing layer
- the next likely work in this area is stronger guidance and evidence-backed explanation

## Evidence, Benchmark, And Commute Roadmap

The next evidence-related work should not be treated as one generic "RAG" project.

It should be split into three tracks.

### 1. Benchmark Layer

Source:

- `document/SDU_median_rents.pdf`

Current finding:

- this PDF yields extractable text
- but it is specifically about subdivided units
- and the document itself says it is for general reference only

What this means:

- this should **not** be treated as a universal market-rent truth source
- it should become a **structured benchmark layer**, not generic vector RAG
- it is suitable only as a narrow SDU benchmark, not as a general district rent benchmark for all listings

Recommended use:

- candidate detail cost context
- compare support note
- light dashboard benchmark hint

Recommended order:

1. extract district-level benchmark data
2. store it as structured data
3. build a `BenchmarkService`
4. detect whether a candidate is likely an SDU using rules first and LLM support second
5. use it only when the candidate type and context make the benchmark meaningful

Current implementation status:

- benchmark evidence MVP is active on candidate detail and compare
- benchmark data is currently served from a versioned local structured data file, not a database table yet
- likely SDU now uses rules plus extraction support

Recommended benchmark rules:

- first version matching can stay at the district level
- benchmark should only be shown when the candidate has a district
- benchmark should only be shown when the candidate is likely an SDU
- benchmark should keep an explicit disclaimer:
  - for subdivided units only
  - general reference only
  - not property-specific

What not to do:

- do not use RAG for this benchmark lookup path
- do not show this benchmark for every listing by default
- do not feed benchmark data directly into the main assessment or hidden compare score

### 2. Tenancy Evidence Layer

Source:

- `document/AGuideToTenancy_ch.pdf`

Current finding:

- simple PDF extraction returns no usable text
- this strongly suggests the PDF is scan-heavy or image-based

What this means:

- this source is **not ready for text RAG yet**
- OCR is a prerequisite
- even after OCR, this should be treated as a narrow explanation-support retrieval layer, not as a main scoring engine

Recommended use after OCR:

- candidate detail clause explanation
- compare briefing evidence note
- future agent guidance support

Recommended order:

1. add OCR
2. inspect OCR quality manually
3. chunk only after the text is acceptable
4. add narrow retrieval for explanation support

Current OCR integration shape:

- OCR belongs in candidate import, not in a separate standalone tool
- users can upload multiple listing, chat, or contract screenshots at once
- OCR output is preserved as source evidence and also merged into the same text bundle used by extraction and assessment
- file storage is abstracted so local development can use filesystem storage now while future deployment can move to object storage without rewriting the analysis flow
- The current backend routes OCR through one service abstraction, so `rapidocr` can stay the fast default while `paddleocr` remains an explicit fallback without changing the import pipeline.
- The default OCR settings now bias toward speed for screenshot-style inputs by disabling document orientation, unwarping, and textline-orientation passes unless you explicitly turn them back on in the backend environment.
- Import no longer waits for OCR and LLM assessment to finish inside one request. The candidate is created first, then OCR and assessment continue in an in-app background task while the detail page polls for progress.
- OCR performance is now improved in three practical ways: the default provider uses RapidOCR on ONNX Runtime for lower CPU overhead, the OCR engine is prewarmed on backend startup, and large uploaded images are resized before OCR.
- If you still use the optional Paddle fallback and see a Windows shell line about a pattern or file not being found while PaddleOCR starts, that message is not emitted by the RentWise codebase itself. It appears to come from the Windows shell or a lower-level dependency layer rather than from our application logging.

Likely value of RAG here:

- explain why a clause or tenancy issue matters
- support a candidate detail evidence note
- support compare briefing rationale

What RAG is unlikely to do well here:

- replace structured extraction
- provide stable legal conclusions
- act as a universal answer engine for every housing question

### 3. Commute Support Layer

Current direction:

- single-destination commute support is the approved first shape
- commute remains support evidence, not a hidden scoring engine

Project-level model needed:

- commute enabled flag
- destination label
- destination query
- commute mode
- max commute minutes

Candidate-level model needed:

- address text
- building name
- nearest station
- location confidence
- location source

Recommended interaction:

- project commute setup is optional, not required at creation time
- candidate location should be extraction-first with user correction when needed
- candidate detail and compare can show commute evidence only when destination and location inputs are strong enough

Recommended order:

1. add project-level commute configuration
2. add candidate-level location evidence
3. update extraction to draft location evidence
4. let users correct location evidence in candidate editing
5. add a narrow map-backed `CommuteService`
6. surface commute evidence in candidate detail and compare

What not to do:

- do not treat district-only data as sufficient for commute estimation
- do not connect map capability before the location model exists
- do not add commute minutes into the main compare score in the first version

## Current Recommendation For The Team

If the team wants to improve the product without bloating it, the best order is:

1. keep reducing information duplication in the current UI
2. add the SDU benchmark layer from the median-rent PDF as structured benchmark data
3. decide whether OCR for the tenancy guide is worth the dependency cost, then only add narrow retrieval if the OCR quality is acceptable
4. add commute only after the project and candidate location models are in place

This is the most honest order.

It keeps the decision workflow stable while adding evidence where it is actually useful.

## Testing

Fast local suite:

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

Real PostgreSQL-backed integration flow:

```bash
cd backend
set RUN_DB_INTEGRATION=1
.\venv\Scripts\python.exe -m unittest tests.integration.test_db_flow
```

The DB-backed test covers:

- register
- create project
- import candidate
- fetch dashboard

The current test suite also covers:

- action-oriented priority ranking
- investigation checklist generation
- top-level candidate recommendation
- compare grouping and compare explanation output
- compare route response shape
- compare briefing fallback behavior
- grouped investigation checklist behavior
- OCR service parsing
- benchmark lookup behavior

## Team Review Notes

Two current product truths are worth keeping in mind during review:

1. More analysis output does not automatically produce better decisions.
   - The product is strongest when the user can tell what to do next within a few seconds.

2. External evidence should support trust, not create fake precision.
   - benchmark data should stay scoped
   - tenancy guide support should wait for OCR
   - commute should wait for a real location model
