# BACKLOG.md — RoleRadarAI Execution State

> This file is the persistent work queue for autonomous Codex/Claude sessions.
>
> **Agents: update this file continuously. Do not rely on conversation memory.**
>
> Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `VERIFYING`, `DONE`, `DEFERRED`.

---

## Current state

```text
Active phase: P14 — Automated discovery (user override; runs before P8)
Active item: P14-003
Last known-good commit: P7 (see Overnight handoff)
Current branch: main
Worktree: clean after P0 commit
Last updated: 2026-10-01
```

## Phase order and authorization

Order (human decision 2026-10-01): **P0 → P1 → P3 → P4 → P2 → P5 → P6 …**

Reason: the human asked for the vertical discovery slice (Next.js → FastAPI → Postgres → workbook import → Companies UI → EURES queue → original-job URL importer) before the resume and OpenJev work. P3 runs before P4, so the EURES queue's "Import job URL" action moved to P4-010.

Authorized: P0, P1, P3, P4, P2, P5, P6, P7 (done). **P14 authorized 2026-10-02** (plan approved: JobSpy + EURES scan override + daily launchd run); stop and report after P14. P8 follows.

Push policy (human decision 2026-10-01): push `main` to `origin` (normal push, never force) after each completed phase.

Decisions: `docs/PRD.md` §82. Open decisions (do not guess): `docs/PRD.md` §83 (OD-1 partly observed, still to confirm before P5; OD-5 future; OD-2/3/4/6 resolved 2026-10-02).

---

# Now

## P0-001 — Bootstrap repository and local development stack

**Phase:** P0  
**Status:** DONE  
**Priority:** P0 / highest

### Goal

Create the initial repository structure for the RoleRadarAI MVP.

### Expected stack

```text
Next.js + TypeScript
FastAPI + Python
PostgreSQL
Redis
Celery
Docker Compose
```

### Acceptance criteria

- [x] repository/workspace initialized;
- [x] Next.js app starts;
- [x] FastAPI app starts;
- [x] PostgreSQL starts locally;
- [x] Redis starts locally;
- [x] worker starts locally;
- [x] API health endpoint returns success;
- [x] frontend can reach backend health endpoint;
- [x] lint/typecheck/test/build commands are documented;
- [x] `.env.example` exists without secrets;
- [x] `AGENTS.md` commands updated to the actual commands;
- [x] `BACKLOG.md` updated;
- [x] changes committed.

### Verification required

```text
frontend lint
frontend typecheck
frontend build
backend lint
backend tests
docker compose startup
health endpoint
```

### Notes / blockers

- OpenJev is not part of Compose (native MLX on host, port 4100 — 4000 is used by another local project).
- Host port 5432 is already taken on the dev machine; Postgres maps to 5433.

### Completion commit

See "Recently completed" (hash recorded after commit).

---

# Next

## P1-001 — Add Company model and migration

**Phase:** P1 — SIRI company foundation  
**Status:** DONE  
**Priority:** P0

### Goal

Create the persistent company model used by the SIRI/EURES workflow.

### Required fields

```text
id
company_name
normalized_name
cvr
siri_certified
siri_source_url
siri_last_seen_at
eures_search_url
eures_status
eures_last_checked_at
eures_notes
website_url
careers_url
ats_provider
active
created_at
updated_at
```

### Critical rule

CVR is a string. Preserve source values exactly.

### Acceptance criteria

- [x] model exists (`apps/api/app/models/company.py`);
- [x] migration exists (`885ccfb342f6`, upgrade/downgrade/`alembic check` verified);
- [x] CVR uniqueness behavior defined/tested (`uq_companies_cvr`);
- [x] repository/service layer follows project conventions;
- [x] tests pass (12);
- [x] committed.

Notes: added `source_position` (SIRI list row ID) for queue order, documented in PRD §14. `eures_status` is VARCHAR + CHECK constraint (not a native PG enum) so the vocabulary can evolve with plain migrations.

### Completion commit

`d0a9428`

---

## P1-002 — Import the SIRI seed workbook

**Phase:** P1  
**Status:** DONE  
**Priority:** P0  
**Depends on:** P1-001

### Goal

Import:

```text
data/siri_certified_companies_eures_queue.xlsx
```

into PostgreSQL.

### Acceptance criteria

- [x] all source rows import (982);
- [x] company names preserved;
- [x] CVR values preserved as strings (incl. `423380281`, `8485085`); numeric CVR cells rejected, never coerced;
- [x] normalized names stored separately (reproduces workbook `Normalized Name` for all 982);
- [x] generated EURES URL equals workbook URL for all 982 rows;
- [x] re-import does not overwrite EURES workflow state;
- [x] no accidental duplicates (duplicate CVRs in a workbook abort the import);
- [x] import is safe to rerun/idempotent;
- [x] tests include unusual CVR values;
- [x] committed.

Entry point: `uv run python -m app.commands.import_siri ../../data/siri_certified_companies_eures_queue.xlsx` (Docker: `docker compose exec api python -m app.commands.import_siri /data/siri_certified_companies_eures_queue.xlsx`).

Deferred: `POST /companies/import/excel` and `POST /companies/import/siri` (PRD §43). The CLI covers the one-time seed; add the upload endpoint (with size limit + MIME validation) when a UI re-import is needed.

### Completion commit

`9a64b1b`

---

## P1-003 — Build Companies API

**Phase:** P1  
**Status:** DONE  
**Depends on:** P1-001, P1-002

### Acceptance criteria

- [x] list companies (`GET /api/v1/companies`, SIRI list order by default; `sort=name|last_checked`);
- [x] pagination (`page`, `page_size` ≤ 200; response `{items,total,page,page_size}`);
- [x] text search (`q`: name ILIKE, normalized name, CVR prefix; LIKE wildcards escaped);
- [x] relevant filters (`eures_status` multi, `checked`, `siri_certified`);
- [x] company detail (`GET /api/v1/companies/{id}`, 404/422);
- [x] tests (52 backend tests total);
- [x] committed.

Completion commit: `d15e238`

---

## P1-004 — Build Companies UI

**Phase:** P1  
**Status:** DONE  
**Depends on:** P1-003

### Acceptance criteria

- [x] Next.js companies page (`/companies`);
- [x] searchable/filterable table (debounced search, EURES status incl. checked/unchecked, sort, SIRI-only; state in URL);
- [x] CVR shown as text (monospace, never coerced);
- [x] SIRI status visible;
- [x] EURES status visible;
- [x] Open EURES action (new tab, `rel="noopener noreferrer"`);
- [x] no job/relevance columns or placeholder actions (PRD §23 phase availability); careers link only when `careers_url` set;
- [x] accessible keyboard interactions (native controls, focus rings, row headers, axe WCAG A/AA clean);
- [x] responsive behavior (wrapping toolbar, horizontally scrollable table container);
- [x] loading/empty/error states (skeleton rows, empty message, alert + retry);
- [x] frontend tests (Vitest 11, Playwright 5 incl. axe);
- [x] committed.

Reusable for P3: `CompanyToolbar`, `CompaniesTable` (`renderActions` prop), `useCompanyQuery`.

Completion commit: `9fc8b5f`

### P1 phase exit (2026-10-01)

All P1 items DONE. Acceptance (IMPLEMENTATION_PLAN §51): 982 rows import; no duplicate CVRs; names match workbook; search + filters work; EURES URL for every company equals the workbook URL; odd CVRs preserved; re-import idempotent and preserves EURES state.

---

# Phase P2 — Resume foundation

## P2-001 — Add Resume and CandidateProfile models

**Status:** DONE  
**Depends on:** P1 phase exit

Start note (2026-10-02): plan for P2 —
- P2-001 models + migration (Resume, CandidateProfile 1:1, single-primary partial unique index);
- P2-002 `StorageProvider` (local dir outside web roots; Docker named volume) + upload validation (extension + magic-byte sniffing, 10 MB cap, sanitized display filename, server-generated storage names);
- P2-003 `ResumeParser` (PyMuPDF / python-docx / UTF-8 text), normalization + SHA-256 `text_hash`, `/resumes` API; extraction failure (e.g. scanned PDF with no text) rejects the upload with a structured error;
- P2-004 profile API + `/settings/profile` UI (manual entry, PRD §14), Playwright "upload resume" flow.

### Acceptance criteria

- [x] Resume model (`app/models/resume.py`; `file_path` is a server-generated storage key, `size_bytes`, `text_hash` indexed);
- [x] CandidateProfile model (1:1 with resume, cascade delete; list fields JSONB default `[]`; languages `[{language, level}]`; `remote_preference` onsite|hybrid|remote|any);
- [x] migration `886b77401096` (round-trip + `alembic check` on `roleradar_test` only);
- [x] primary-resume semantics: partial unique index `uq_resumes_single_primary` (at most one primary);
- [x] tests (5; 174 backend total).

Refactor: enum column helper moved to `app/db/types.py::str_enum` (shared by job and resume models).

Completion commit: `673043f`

---

## P2-002 — Implement resume upload and secure storage

**Status:** DONE  
**Depends on:** P2-001

### Acceptance criteria

- [x] PDF, DOCX, TXT accepted (`app/services/resume_files.py::validate_upload`);
- [x] MIME validation by extension **and** magic bytes (client content type ignored): `%PDF-`; DOCX = zip with `[Content_Types].xml` + `word/document.xml` (zip-bomb guard: ≤ 50 MB uncompressed, ≤ 2000 entries); TXT = UTF-8 / BOM'd UTF-16, no NUL bytes;
- [x] file-size limit 10 MB (`FILE_TOO_LARGE`, 413); empty file rejected;
- [x] filenames sanitized for display only (basename, NFKC, no control chars, ≤ 120 chars); storage keys are server-generated random names;
- [x] files outside public web directories: `StorageProvider` boundary (`app/providers/storage.py`), `LocalStorageProvider` under `UPLOAD_DIR` (dirs 0700, files 0600, atomic writes, path-traversal-proof keys); Docker named volume `uploads` at `/var/lib/roleradar/uploads`;
- [x] structured `AppError` base (`app/core/errors.py`) now shared by upload and job-source errors;
- [x] tests (35; 209 backend total). Samples generated in-process (`tests/resume_samples.py`), no real personal data.

Completion commit: `f76b9fb`

---

## P2-003 — Extract resume text

**Status:** DONE  
**Depends on:** P2-002

### Acceptance criteria

- [x] PDF extraction (PyMuPDF, reading order, ≤ 50 pages; password-protected / damaged → clear error);
- [x] DOCX extraction (python-docx; paragraphs and tables in document order);
- [x] normalized text (NFKC incl. ligatures, newlines, control chars, whitespace);
- [x] content hash (`text_hash` = sha256 of normalized text);
- [x] extraction errors surfaced cleanly (`RESUME_EXTRACTION_FAILED`; < 50 chars = scanned-PDF hint; nothing stored on failure);
- [x] `/resumes` API: upload (multipart), list, detail, set-primary, delete (file removed; newest promoted); `ResumeParser` + `StorageProvider` injected as FastAPI dependencies;
- [x] new resume's profile copies the current primary profile (user's own entries, never AI);
- [x] resume text never logged (test);
- [x] tests (22; 231 backend total).

Completion commit: `d071ef3`

---

## P2-004 — Candidate profile review/edit UI

**Status:** DONE  
**Depends on:** P2-003

- [x] `GET/PATCH /resumes/{id}/profile` (partial update; lists trimmed + de-duplicated; years 0–60 with ≤ 1 decimal; languages with CEFR level A1–C2/Native; unknown fields rejected);
- [x] `/settings/profile` (+ `/settings` redirect, sidebar "Settings"): upload form, resume table (view, make primary, delete with confirm), extracted-text viewer, profile editor (tag inputs, languages rows, remote preference, years), save / discard, loading/empty/error states;
- [x] bug found by E2E and fixed: the "Saved" confirmation never appeared because the editor remounted after saving;
- [x] tests: backend 13 (244 total), Vitest 10 new (37 total), Playwright 3 new + axe on `/settings/profile` (15 total).

### P2 phase exit (2026-10-02)

All P2 items DONE. Acceptance (IMPLEMENTATION_PLAN §52): user uploads PDF → text extraction succeeds → extracted content visible → structured profile editable → resume survives restart (verified: Playwright reload; Docker API container recreated with the resume, profile and 0600 file intact, then cleaned up via the API).

Completion commit: this commit.

### Fields

```text
target roles
skills
years experience
industries
education
certifications
languages
preferred locations
remote preference
work authorization
```

AI extraction must remain editable.

---

# Phase P3 — EURES discovery workflow

## P3-001 — Add EURES queue state to backend

**Status:** DONE

**Depends on:** P1 phase exit

### Status vocabulary

```text
NOT_CHECKED
OPENED
CHECKED_NO_JOBS
JOB_FOUND
ERROR
```

### Acceptance criteria

- [x] transition endpoints per PRD §8 (opened, no relevant jobs, error, reset, notes); see PRD §43;
- [x] OPENED never downgrades a completed status;
- [x] next-unchecked endpoint (NOT_CHECKED or OPENED, SIRI order, `after_position`, wraps around);
- [x] queue stats (total / checked / remaining / by_status);
- [x] tests (69 backend tests total).

Notes: `eures_status` cannot be PATCHed directly, only through transition endpoints. Structured log events `eures_opened`, `eures_no_relevant_jobs`, `eures_error`, `eures_reset`, `eures_notes_updated`.

Completion commit: `850fe2b`

---

## P3-002 — Build EURES discovery queue UI

**Status:** DONE  
**Depends on:** P3-001, P1-004

### Acceptance criteria

- [x] list SIRI companies (`/eures`, defaults to unchecked; reuses P1 table/toolbar);
- [x] search/filter;
- [x] open company-specific EURES search (new tab; records `OPENED`);
- [x] record opened/checked state (stats bar: companies / checked / remaining);
- [x] mark no relevant jobs, mark error, reset;
- [x] add note (native `<dialog>`; notes shown under company name);
- [x] next unchecked company ("Next unchecked company" panel from server state; Skip keeps `?after=` in URL);
- [x] state persists after browser restart (server state; Playwright reload check);
- [x] tests (Vitest 19 total; Playwright 8 total incl. axe on /eures).

The same row actions now also appear on `/companies` (PRD §23 phase availability for P3).

Original-job import moved to P4-010.

### P3 phase exit (2026-10-01)

P3-001 and P3-002 DONE. Acceptance (IMPLEMENTATION_PLAN §53, as amended): start with company 1 → open its EURES search (OPENED) → return → mark completed (CHECKED_NO_JOBS) → continue to the next unchecked company → refresh → state unchanged → counters correct. Verified by `tests/e2e/eures-queue.spec.ts`. The "import an employer vacancy" step belongs to P4-010.

---

# Phase P4 — Job ingestion

## P4-001 — Add Job and JobSource models

**Status:** DONE

Start note: models per PRD §15 decisions (nullable `company_id`, JobSource snapshots, `source_update_pending` instead of overwriting). Requirement JSONB columns deferred to P5 (extraction belongs to the job-processing graph).

- [x] `Job` + `JobSource` models, migration `5dc852feacfc` (round-trip + `alembic check` verified on `roleradar_test`);
- [x] JobSource = snapshot, `UNIQUE(source_url, content_hash)`, status ACCEPTED/PENDING/REJECTED (PRD §15 revised);
- [x] tests (74 backend total).

**Incident 2026-10-01:** while verifying this migration, a chained `alembic downgrade -1` ran against the **dev DB** after a failed upgrade and dropped `companies`. The dev DB was rebuilt and reseeded (982 companies, all NOT_CHECKED, new UUIDs); any EURES progress recorded before then is lost. Prevention rules added to AGENTS.md §7.

Completion commit: `77311fe`

---

## P4-002 — Add URL-import security layer

**Status:** DONE  
**Priority:** P0

### Mandatory

- [x] HTTP/HTTPS only, default ports only, no credentials (`app/connectors/http.py`);
- [x] DNS/IP validation; all resolved addresses must be public; connection pinned to the validated IP (Host + SNI), so no DNS-rebinding window;
- [x] block localhost (incl. `*.localhost`, `.local`, `.internal`);
- [x] block private/link-local/CGNAT/IPv4-mapped IPv6 networks;
- [x] block metadata endpoints (169.254.169.254 et al.);
- [x] validate redirects (manual, ≤5 hops, each re-validated);
- [x] bounded response sizes (5 MB)/timeouts (10 s);
- [x] EURES hosts rejected (`EURES_NOT_ALLOWED`);
- [x] robots.txt policy for generic pages (`app/connectors/robots.py`, RFC 9309: 4xx allow, 5xx disallow);
- [x] structured, retry-classified errors (`app/connectors/errors.py`);
- [x] tests (44, no network) + one live sanity check (TLS via pinned IP, redirect, `localtest.me` → blocked).

Completion commit: `a13c944`

---

## P4-003 — Implement `JobSourceConnector` abstraction

**Status:** DONE  
**Depends on:** P4-001, P4-002

- [x] `JobSourceConnector` protocol + `ExternalJob` / `NormalizedJob` (`app/connectors/base.py`), incl. `can_handle_url` / `fetch_job_by_url` (PRD §9);
- [x] `UrlImportConnector` base raising `UnsupportedOperation` for company search;
- [x] `ConnectorRegistry` (validates URL first, then first matching connector);
- [x] `EuresDiscoveryConnector` (search URL only; every retrieval method refuses);
- [x] `html_to_text` / `clean_text` (descriptions stored as plain text);
- [x] tests (8).

Completion commit: `d489b1d`

---

## P4-004 — Implement JSON-LD `JobPosting` connector

**Status:** DONE  
**Depends on:** P4-003

- [x] `app/connectors/jsonld.py`: finds JobPosting in any ld+json block, `@graph`, list `@type`, comment/CDATA wrapped; malformed JSON skipped;
- [x] fields: title, plain-text description (escaped HTML handled), hiringOrganization, multi-location, country (code or name, as given), employmentType, TELECOMMUTE → remote, identifier, url, datePosted/validThrough;
- [x] `EmployerPageConnector` (robots.txt checked, incl. cross-host redirect target; HTML only); incomplete data → `EXTRACTION_FAILED` with manual-paste hint;
- [x] fixtures `tests/fixtures/jobs/jsonld_*.html`; tests (7).

Completion commit: `89b5418`

---

## P4-005 — Implement Greenhouse connector

**Status:** DONE (with P4-006/P4-007 in one commit `150ea80`)  
**Depends on:** P4-003

Verified 2026-10-01 (live probe, read-only): `GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}` (content is HTML-escaped). Hosted URLs `job-boards.greenhouse.io/{board}/jobs/{id}` (and legacy `boards.greenhouse.io`). `boards-api.eu.greenhouse.io` does not resolve → EU-hosted boards fall back to the employer-page connector. Company-site URLs with `?gh_jid=` have no board token → employer-page connector.

---

## P4-006 — Implement Lever connector

**Status:** DONE (see P4-005)  
**Depends on:** P4-003

Verified 2026-10-01: `GET https://api.lever.co/v0/postings/{site}/{id}` (EU: `api.eu.lever.co`); hosted `jobs.lever.co/{site}/{id}` / `jobs.eu.lever.co`.

---

## P4-007 — Implement Ashby connector

**Status:** DONE (see P4-005)  
**Depends on:** P4-003

Verified 2026-10-01: `GET https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true` (board-level only; filter by job id); hosted `jobs.ashbyhq.com/{org}/{id}`.

P4-005..007 result: `app/connectors/ats.py`; sanitized fixtures `greenhouse_job.json`, `lever_job.json`, `ashby_board.json` (real field shapes, invented content); 15 tests. Lever and Ashby APIs do not state the employer name, so `employer_name` stays None and company linking relies on import context. Compensation is not parsed (stored in the raw payload only).

---

## P4-008 — Implement generic permitted job-page fallback

**Status:** DONE  
**Depends on:** P4-003

- [x] used only when no JSON-LD JobPosting exists; title h1 → og:title → <title>; description from main/article/[role=main]/#content/body minus nav/header/footer/aside;
- [x] < 200 chars or no title → `EXTRACTION_FAILED` (manual paste); location never guessed from free text;
- [x] fixtures `generic_page.html`, `generic_too_short.html`; tests (2).

Completion commit: `9b93073`

---

## P4-009 — Implement job normalization/deduplication

**Status:** DONE

### Dedup inputs

```text
normalized company
normalized title
location
content hash
```

- [x] `app/services/job_import.py`: content hash (normalized title/employer/location + whitespace-collapsed description), `dedup_key` per PRD §27 (company key = linked company's normalized name, else normalized employer name);
- [x] outcomes: created / attached_source (same vacancy, new URL) / unchanged / update_pending (PENDING snapshot; accept/reject endpoints, 409 on duplicate);
- [x] company link: explicit `company_id` → link + `JOB_FOUND` + last_checked; otherwise exact normalized employer match only (single match), status untouched;
- [x] manual JD paste (`/jobs/import-text`; reference URLs validated, EURES rejected);
- [x] `/jobs` list/detail/delete; `Company.jobs_count`; `has_jobs` filter; structured SourceError responses;
- [x] structured log events `job_import_started|completed|failed` with duration;
- [x] tests (19; 169 backend total).

Note: imports run synchronously in the request (target < 10 s); Celery batching is P7.

Completion commit: `a375c59`

---

## P4-010 — Import job URL from the EURES queue

**Status:** DONE  
**Depends on:** P3-002, P4-003..P4-009

### Acceptance criteria

- [x] "Import job" on each EURES queue row, the current-company panel and Companies rows (URL or manual paste; robots/extraction failures switch to paste with the URL prefilled);
- [x] imported job linked to that company;
- [x] company becomes `JOB_FOUND`;
- [x] Jobs column (links to `/jobs?company=`) + Has jobs filter on Companies/EURES;
- [x] `/jobs` list and `/jobs/[id]` detail (plain-text description, sources, accept/keep source updates, delete);
- [x] less frequent actions (note, error, reset) in a native popover "More" menu;
- [x] Playwright flow: open EURES → EURES URL refused → paste → view job → queue moved on → company shows Job found (11 e2e incl. axe on /jobs).

Bug found by E2E and fixed: refreshing lists right after an import moved the queue to the next company while the dialog stayed open under the wrong company name. Lists now refresh when the dialog closes, and row actions are keyed by company.

### P4 phase exit (2026-10-01)

All P4 items DONE. Acceptance (IMPLEMENTATION_PLAN §54): supported URLs produce title, company, description, location, apply URL, source (fixture tests for JSON-LD, generic, Greenhouse, Lever, Ashby + live check on Lever/Greenhouse); duplicate imports give one canonical job; EURES URLs rejected; robots disallow → manual paste; changed content → snapshot, not overwrite; queue import → JOB_FOUND.

---

# Phase P5 — OpenJev matching

**Decisions resolved 2026-10-02:** OD-1 (contract confirmed, PRD §29), OD-2, OD-3, OD-4, OD-6 (PRD §18, §19, §21, §82). Implementation decisions in PRD §29 "P5 implementation decisions".

**Depends on:** P2 (done).

Plan (2026-10-02): P5-001+P5-003 provider + `/health/openjev` → P5-004 rubric_v1 + pure scoring → P5-005/P5-006 MatchScore, cache key, queue (Celery + inline), `/jobs/{id}/score`, `/matches` → P5-007 Score job UI on the job page + E2E against a fake OpenJev → live run against the real model.

## P5-001 — Define `DecisionProvider`

**Status:** DONE (with P5-003, commit `64a5ed8`)

- [x] `app/providers/decision.py`: generic `DecisionProvider` (`model_info()`, `decide(state, questions)`), typed `ScoreQuestion` / `YesNoQuestion` and validated answers; errors `DECISION_PROVIDER_UNAVAILABLE` (retryable, 503), `DECISION_REQUEST_REJECTED`, `DECISION_INVALID_RESPONSE`.

---

## P5-002 — Run/configure OpenJev local service

**Status:** DONE (2026-10-01, outside the repo)

Endpoint: `http://127.0.0.1:4100/v1/systemone` (Docker: `http://host.docker.internal:4100`). The upstream default 3000 is the RoleRadarAI web app; 4000 is another local project.

- Weights in `~/models/openjev/openjev-MLX-4bit`, all SHA256SUMS verified; helper `openjev-api/helper/shim*.py` at the README-pinned revision (sha 81a22f1b), reviewed: stdlib HTTP server bound to 127.0.0.1, no shell exec.
- `~/models/openjev/start-openjev.sh` / `stop-openjev.sh` run the README command with `--port 4100` (nohup, pid file, `openjev.log`).
- Smoke test: choice + noul questions on a resume/JD pair returned sensible answers (skills "strong" 0.58; mandatory Danish B2 met 0.012).
- **Performance risk:** 55–87 s per 2-question request on the 24 GB Mac because swap was ~97% full (14 GB model + Docker VM 7.75 GB + desktop apps). Expected ~seconds with enough free memory. P5/P7 must treat scoring as async with generous timeouts regardless (PRD §69).

Do not commit model weights into Git.

---

## P5-003 — Implement `OpenJevProvider`

**Status:** DONE (with P5-001)  
**Depends on:** P5-001, P5-002

- [x] `app/providers/openjev.py`: httpx client to `OPENJEV_BASE_URL` (not the SSRF fetcher), connect 5 s / read `OPENJEV_TIMEOUT_SECONDS` (1800 s), retries only transport failures (2×), 5xx → unavailable, 4xx → rejected, response validated (all questions answered, correct types, probabilities in [0,1]);
- [x] `model_revision` from `/v1/version` (model dir, calibration, helper sha, flags hash);
- [x] `GET /api/v1/health/openjev` (200 with revision / 503);
- [x] tests with a wire-compatible fake (`tests/fake_openjev.py`): 11 (255 backend total).

---

## P5-004 — Define rubric v1

**Status:** DONE (commit `3bee949`)

- [x] `app/matching/rubric.py`: `RUBRIC_V1` config (levels, weights summing to 1.0, six hard-requirement types with stated/met questions, thresholds 0.5 / 0.75, bands 85/70/55, input caps); questions say "judge only from the text";
- [x] `app/matching/scoring.py`: pure functions — dimension = level/4×100, requirement labels (boundaries PARTIAL), must-have = mean met-probability of stated types, weight rescaling when none stated, BLOCKED category with unchanged score, bands on the rounded score, two-phase question sets;
- [x] tests (24; 279 backend total).

Initial dimensions:

```text
must-have coverage
skills fit
experience fit
role alignment
seniority alignment
domain alignment
education/certification
```

Application code owns weights.

---

## P5-005 — Persist match results

**Status:** DONE (with P5-006, commit `d6216f0`)

- [x] `MatchScore` model + migration `f8b28895d5f0` (round-trip + `alembic check` on `roleradar_test` only): status QUEUED/RUNNING/DONE/FAILED, all input hashes, model provider/name/revision, rubric version, seven 0–100 dimensions, blocker flag, per-requirement checks, matched/partial/missing lists, explanation (per-dimension probabilities, tokens, truncation), errors, attempts, timings; cascades with job and resume;
- [x] `match_service`: request (cache / in-flight / new), two-phase run (dimensions + "stated?" → "met?" only for stated types), deferred on provider outage, `INPUT_CHANGED` guard, structured logs `match_started|completed|failed|deferred`;
- [x] queue: `CeleryMatchQueue` (`roleradar.score_match`, acks_late, 2 retries with backoff on provider outage, 1 h limit) and `InlineMatchQueue` (`MATCH_QUEUE=inline`);
- [x] API: `POST /jobs/{id}/score` (200 cached/in-flight, 202 queued, 409 no primary resume, 503 OpenJev or queue down), `GET /matches/{id}`, `GET /matches?job_id=&resume_id=`.

Persist:

```text
resume hash
job hash
model
model revision
rubric version
dimension results
matched requirements
missing requirements
uncertain requirements
overall score
```

---

## P5-006 — Implement score caching/invalidation

**Status:** DONE (with P5-005)

- [x] `input_hash` = sha256(resume text hash, profile hash, job content hash, model revision, rubric version); partial unique index `uq_match_scores_live_input` (non-FAILED) also prevents duplicate concurrent scoring;
- [x] tests: identical input cached; resume, profile, job content, model revision and rubric version each invalidate; in-flight not duplicated; FAILED never blocks a retry (20 tests; 299 backend total).

Cache key must change when:

```text
resume changes
job content changes
model revision changes
rubric version changes
```

---

# Phase P6 — Ranked matching experience

## P5-007 — Score job action and result panel

**Status:** DONE (commit `86f6944`)

P5 acceptance needs a "Score Job" action that shows all dimensions; the full ranked experience stays in P6.

- [x] Match panel on `/jobs/[id]`: "Score against my resume", queued/running status with elapsed time and 3 s polling, result (score / 100, category or "Blocked: … not met", seven 0–100 dimension bars with n/a for an unstated must-have, stated requirements with ✓/△/✗ and probabilities, unstated types listed, model + rubric + duration, "not a chance of being hired"), failure with retry, clear messages for no resume / OpenJev down;
- [x] E2E: isolated stack now on ports 3200/8200 with a wire-compatible fake OpenJev (`tests/fake_openjev_server.py`, :4299) and `MATCH_QUEUE=inline`; flow: score → running → blocked result with all dimensions → reload → cached; cleans up after itself;
- [x] tests: Vitest 4 new (41 total), Playwright 1 new (16 total).

---

### P5 phase exit (2026-10-02)

All P5 items DONE. Acceptance (IMPLEMENTATION_PLAN §55): "Score job" produces all dimensions (E2E + live); result survives restart (persisted; E2E reload; Docker); identical input uses the cache; resume, profile, job content, model revision and rubric version each invalidate it (tests).

**Live run on the real OpenJev (2026-10-02, Docker worker, anonymized sample resume + test job, both deleted afterwards):** 80.1 / 100, category BLOCKED (mandatory Danish C1: met 0.0097); years of experience MET (0.987), work location MET (0.918); other three types not stated; dimensions skills 92, experience 84, role 94, seniority 90, domain 64, education 79, must-have 64. Took **738 s**: phase 1 = 12 questions / 4,917 tokens in 575 s, phase 2 = 3 questions in 162 s (≈ 40–50 s per question while macOS swapped ~16 GB).

---

Plan (2026-10-02), implementation decisions (implementation-local, reversible):
- Job gets `status` NEW | SAVED | IGNORED (PRD §15 said P6). "Applied" belongs to P8 application tracking, so the Applied / Not applied filters arrive in P8. Ignored jobs are hidden unless the status filter asks for them.
- A job's Match = its latest DONE match for the **primary** resume. Ranking: by score with blocked jobs below unblocked ones by default (OD-3), toggle to mix; unscored jobs last.
- A match is flagged **outdated** when the resume text, profile, job content or rubric changed since it was scored (model revision is not checked offline). Outdated scores still show, with a "Score again" prompt.
- One listing endpoint (`GET /jobs` with match fields, filters and sorts) serves both `/jobs` and the ranked `/matches` view.
- Dashboard shows only data that exists today (companies, checked, jobs, scored, strong matches, saved, needs review); Applications / Interviews arrive with P8.

## P6-001 — Build Jobs list

**Status:** DONE (backend `591cc3d`; UI in the P6 UI commit)

- [x] `/jobs`: filter toolbar (role/company, location/country, status, min match, blocked mode, source, sort, SIRI only; URL state), columns Role, Company, Location, Source, Published, Match (score + category + outdated / scoring), Save/Ignore/Restore;

Backend:
- [x] `Job.status` NEW|SAVED|IGNORED + migration `1818d540c7c5` (explicit `ck_jobs_job_status`; round-trip on `roleradar_test` only); `PATCH /jobs/{id}` {status};
- [x] `GET /jobs` returns each job's current Match (latest DONE for the primary resume, via `DISTINCT ON`), `match_outdated`, `scoring`; filters q (title/employer/company), location (location/city/country), company_id, source_type, siri_only, status (default NEW+SAVED), scored, min_score, blocked (last|mixed|exclude), category, update_pending; sorts match|newest|company|title;
- [x] `MatchRead.outdated`;
- [x] tests (17; 316 backend total).

---

## P6-002 — Build Matches list

**Status:** DONE

- [x] `/matches`: 20 per screen, ranked (#), Match, Role, Company, Location, Gaps (✗ missing / △ partial), actions; blocked below by default with "Rank by score" / "Hide"; category filter (`?cat=STRONG`) with a clear link; sidebar "Matches";
- [x] acceptance (IMPLEMENTATION_PLAN §56): "What are the 20 strongest jobs I've found?" answered on one screen (E2E `ranking.spec.ts`).

Support:

```text
score sorting
company filter
title filter
country/location filter
SIRI-only filter
saved/applied status
```

---

## P6-004 — Dashboard

**Status:** DONE

- [x] Tiles: SIRI companies, companies checked, active jobs, scored jobs, strong matches (stored category, links to `/matches?cat=STRONG`), saved jobs; Top matches (5), Recently discovered (5), Needs review (unscored, changed postings, companies left on EURES); counts reuse `/eures/stats` and `/jobs` totals (no new endpoint).

PRD §33, limited to existing data (see plan above).

---

## P6-003 — Build Job detail / evidence screen

**Status:** DONE (evidence panel from P5-007, plus:)

- [x] Save / Ignore / Restore and a status badge on the job page; "Outdated" notice with "Score again" when inputs changed;
- [x] tests: Vitest 7 new (48 total); Playwright `ranking.spec.ts` (blocked last / mixed / hidden, save, ignore, restore, dashboard tiles + strong-matches link, outdated after a profile edit) + axe on `/matches` (18 total). Fake OpenJev gained `FAKE_LEVEL=` / `FAKE_BLOCK` markers.
- [x] a11y fix found by axe: inline link in the Matches empty state was colour-only (now underlined).

### P6 phase exit (2026-10-02)

All P6 items DONE. Dashboard, jobs table, matches table, job details, filters, sorting, saved and ignored jobs work; the 20 strongest jobs fit on one screen. Applied / Not applied filters wait for P8 application tracking.

Display:

```text
overall Match Score
dimension scores
matched requirements
partial requirements
missing requirements
unknowns
original source link
```

Never label the score as hiring probability.

---

# Phase P7 — Background/bulk processing

Plan and implementation decisions (2026-10-02, implementation-local):
- **Match run** = one batch over a scope of jobs for the primary resume: `unscored`, `unscored_or_outdated` (default) or explicit `jobs`. New `match_runs` + `match_run_items` tables record per-job outcome (scored / cached / skipped as not relevant / failed).
- **Relevance filter (PRD §28 step 1):** a job is relevant when every word of at least one profile target role appears in the job title (normalized, accents folded). Only these go to OpenJev. No target roles → filter off (stated in the run). It can be switched off per run; a single "Score job" click is never filtered.
- **Sequential:** one Celery task walks the run job by job (OpenJev serializes anyway); cancel stops after the current job. One active run at a time.
- **Retry classification (P7-004):** OpenJev unavailable / timeout / 5xx → bounded exponential backoff (30 s, 60 s, 120 s); rejected / invalid response / input changed / job deleted → no retry, the job fails and the run continues (PRD §65). If OpenJev stays unavailable after the retries, the run stops (FAILED) and the remaining jobs are marked skipped, instead of burning retries on every job; starting a new run resumes (finished jobs come from the cache). Job-import errors already carry the same `retryable` classification (P4); there is no bulk import in the MVP.
- **Progress:** `GET /match-runs/{id}/events` (SSE, PRD §44) with polling fallback in the UI; time estimate from the average duration of recent scores.
- The batch run task is not `acks_late` (a redelivery after Redis's visibility timeout would start a second walker); Redis visibility timeout raised to 4 h for the per-job task.

## P7-001 — Add Celery task framework

**Status:** DONE (backend commit; UI in P7-003)

- [x] Celery tasks `roleradar.score_match` (acks_late, 2 retries) and `roleradar.match_run` (not acks_late, no time limit); Redis `visibility_timeout` 4 h; inline queue for tests / worker-less runs.

---

## P7-002 — Add match-run queue

**Status:** DONE

- [x] `match_runs` / `match_run_items` (migration `2c4db9b939ad`, round-trip on `roleradar_test` only);
- [x] `app/matching/relevance.py` (PRD §28 step 1, all target-role words in the title; 11 tests);
- [x] `match_run_service`: plan (scope unscored / unscored_or_outdated / jobs; ignored and in-flight jobs excluded), create (one active run; NOTHING_TO_SCORE), sequential execute (cache → CACHED, in-flight → wait, else score), cancel, fail_run, progress with time estimate from the last 20 scores;
- [x] API: `POST /match-runs/preview`, `POST /match-runs` (202), `GET /match-runs`, `GET /match-runs/{id}`, `POST /match-runs/{id}/cancel`.

---

## P7-003 — Add SSE progress updates

**Status:** DONE

- [x] `GET /match-runs/{id}/events`: `progress` event whenever the run changes, `: keepalive` every 15 s, `end` when finished (poll interval `RUN_EVENTS_POLL_SECONDS`).
- [x] UI: "Score jobs in bulk…" on Matches and Jobs → preview dialog (scope, title filter, target roles, jobs to score / skipped, time estimate) → live panel (status, n of N, ETA, current job, progress bar, cancel) via EventSource with polling fallback → summary (scored / up to date / skipped / failed with reasons, dismiss); job lists refresh as each job finishes;
- [x] tests: Vitest 4 new (52 total); Playwright `batch.spec.ts` (relevance filter, live progress, ranked result, irrelevant job never scored, nothing left to score) — 19 total.

### P7 phase exit (2026-10-02)

All P7 items DONE (IMPLEMENTATION_PLAN §57): Celery tasks, Redis queue, task status, retry policy with bounded exponential backoff and no retry for invalid/rejected input, SSE progress, batch matching. Docker check: worker registers `roleradar.match_run` and executes it (unknown run id → clean no-op). A full real-model batch was not run (≈ 12 min per job on this Mac and runs use the primary resume); the per-job OpenJev path is the one verified live in P5.

---

## P7-004 — Add retry classification

**Status:** DONE

- [x] OpenJev unavailable / timeout / 5xx → backoff `MATCH_RETRY_DELAYS_SECONDS` (30, 60, 120); invalid response / rejected / input changed / job gone → no retry, only that job fails; persistent outage stops the run (remaining jobs SKIPPED). Tests: 14 in `test_match_runs.py` (341 backend total).

Retry:

```text
network timeout
temporary 5xx
temporary OpenJev unavailable
```

Do not retry blindly:

```text
invalid URL
404
validation failure
unsupported source
```

---

# Phase P14 — Automated discovery (user override, PRD §84)

Plan: `~/.claude-work/plans/okay-that-is-good-sequential-raccoon.md` (approved 2026-10-02). Runs before P8.

## P14-001 — Record the override and guardrails in the docs

**Status:** DONE — PRD §8/§9/§26 notes, new §84, §82 rows, OD-7; AGENTS §5; COMMIT_PROTOCOL §28.

## P14-002 — Spike: EURES endpoints, robots.txt, fixtures (OD-7)

**Status:** BLOCKED (2026-10-02)

Found (3 polite requests, 10 s apart): `europa.eu/robots.txt` does not disallow `/eures/` but sets **Crawl-delay: 10** for `*` → any scan must wait ≥ 10 s between requests. The search page (`/eures/portal/jv-se/search`) is an Angular SPA; its data endpoints are not in `main-*.js` / `jv-se.routes-*.js` (configured at runtime). No WAF/captcha seen on the HTML.

Blocked by: the agent's attempt to identify the data endpoints by loading the page in headless Chromium and recording its requests was **denied by the Claude Code permission classifier**. The agent did not pursue the endpoints another way.

What would resolve it (human decision): either (a) the user reads the search + vacancy-detail requests from their own browser devtools (Network tab, one EURES search) and records them in OD-7, or (b) the user grants permission for the headless-browser spike, or (c) drop the EURES scan and rely on JobSpy + SIRI linking.

Safe work completed: robots/crawl-delay recorded; P14-005 stays unimplemented; the discovery run reports the EURES source as unavailable.

Exact next step after unblock: save sanitized search/detail fixtures under `apps/api/tests/fixtures/eures/`, then build P14-005.

## P14-003 — Source types, discovery settings and run models

**Status:** TODO

## P14-004 — JobSpy source (Indeed DK, LinkedIn, Google) + cross-board dedup

**Status:** TODO

## P14-005 — EURES scan source (per company, rotation, status updates)

**Status:** BLOCKED — depends on P14-002 (OD-7). Must honour Crawl-delay 10 s.

## P14-006 — Discovery orchestrator, time budget, Celery task, API + SSE

**Status:** TODO

## P14-007 — Discover page (settings, Search now, progress, results)

**Status:** TODO

## P14-008 — Daily automation (script + launchd; install only after the user picks a time)

**Status:** TODO

---

# Phase P8 — Application tracking

## P8-001 — Application model/state machine

**Status:** TODO

Canonical states:

```text
DISCOVERED
SAVED
PREPARING
APPLIED
RECRUITER_SCREEN
INTERVIEW
FINAL_INTERVIEW
OFFER
REJECTED
WITHDRAWN
EXPIRED
```

---

## P8-002 — Application UI

**Status:** TODO

---

# Phase P9 — Generative provider

## P9-001 — Define `GenerationProvider`

**Status:** TODO

Do not bind core business logic directly to one vendor.

---

# Phase P10 — LangGraph application pack

## P10-001 — Define application-pack graph state

**Status:** TODO

---

## P10-002 — Context builder

**Status:** TODO

---

## P10-003 — Resume tailoring node

**Status:** TODO

---

## P10-004 — Cover-letter node

**Status:** TODO

---

## P10-005 — Outreach node

**Status:** TODO

Outputs may include:

```text
LinkedIn connection note
LinkedIn recruiter DM
Recruiter email
Hiring-manager email
```

---

## P10-006 — Interview-preparation node

**Status:** TODO

---

## P10-007 — Fact-checker node

**Status:** TODO  
**Priority:** P0 when P10 starts

All candidate factual claims must be supported by the master resume/profile.

---

## P10-008 — Human approval checkpoint

**Status:** TODO

No generated application content is automatically sent.

---

# Phase P11 — AI workspace

## P11-001 — Build job-specific AI workspace

**Status:** TODO

Suggested sections:

```text
Overview
Resume
Cover letter
LinkedIn
Email
Interview
```

---

# Phase P12 — Feedback / evaluation dataset

## P12-001 — Add recommendation feedback

**Status:** TODO

Capture:

```text
good recommendation
bad recommendation
applied
would not apply
reason
```

---

## P12-002 — Add offline ranking evaluation

**Status:** TODO

Candidate metrics:

```text
Precision@10
Precision@20
NDCG@20
```

Do not fine-tune a matching model before a trustworthy evaluation set exists.

---

# Phase P13 — Authorized EURES integration

## P13-001 — Add authorized connector when access is available

**Status:** DEFERRED

### Blocker

Requires appropriate authorized data-access path.

### Architecture requirement

The new connector must fit the existing `JobSourceConnector` boundary without forcing changes to matching/application layers.

---

# Meta / documentation

## META-001 — Save final PRD to repository

**Status:** DONE (commit `bb18c1a`)  
**Note:** `plan.md` split into `docs/PRD.md` (product + decisions §82/§83) and `docs/IMPLEMENTATION_PLAN.md` (phases §50–63, §71, §74–78).  
**Priority:** P0

Expected path:

```text
docs/PRD.md
```

---

## META-002 — Save phased implementation plan

**Status:** DONE (commit `bb18c1a`)  
**Priority:** P0

Expected path:

```text
docs/IMPLEMENTATION_PLAN.md
```

---

## META-003 — Create architecture document

**Status:** DONE (commit `bb18c1a`)  
**Priority:** P0

Expected path:

```text
docs/ARCHITECTURE.md
```

Include:

```text
system diagram
service boundaries
database entities
provider interfaces
job-ingestion flow
matching flow
LangGraph flow
security boundaries
```

---

# Blocked

None yet.

When adding blockers, use:

```text
## <ID> — <title>

Status: BLOCKED
Blocked by:
Why:
What is needed:
Safe work completed:
Exact next step after unblock:
```

---

# Recently completed

Move completed items here rather than deleting history.

## P0-001 — Bootstrap repository and local development stack

Status: DONE
Completed: 2026-10-01
Commit: `f7845b2`
Validation:
- backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (strict), `uv run pytest` (5 passed) — PASS
- frontend: `pnpm lint`, `pnpm typecheck`, `pnpm test` (2 passed), `pnpm build` — PASS
- `docker compose up -d --build`: postgres, redis, api (healthy), worker, web all up
- `GET /api/v1/health` 200, `GET /api/v1/health/database` 200, web 200, CORS for :3000
- Celery round-trip `roleradar.ping` via Redis → "pong"
- `pnpm test:e2e` (Playwright: dashboard shows "API connected") — PASS
Notes:
- Python 3.13 (plan says 3.12+; 3.13 is what the machine has via uv).
- Next.js 16.3 (async `params`/`searchParams`; ESLint CLI instead of `next lint`).
- Own Tailwind primitives instead of shadcn CLI (PRD §10 allows "or equivalent").
- `apps/web/AGENTS.md` / `CLAUDE.md` are generated by Next.js and re-created by `next dev`; keep them.

## META-001..003 — PRD, implementation plan, architecture

Status: DONE
Commit: `bb18c1a`

Use:

```text
## <ID> — <title>

Status: DONE
Completed:
Commit:
Validation:
Notes:
```

---

# Overnight handoff

## P7 run (latest)

```text
Last updated: 2026-10-02
Last commit: see `git log -1`; pushed to origin/main with this phase
Current branch: main
Worktree: clean
Active phase: none — P0, P1, P3, P4, P2, P5, P6, P7 complete
Status: STOPPED for human review

Completed this run:
- P7 backend: relevance filter, match runs, retries, SSE, Celery run task (b09b739)
- P7-003 UI: batch dialog + live panel; docs (this commit)

Validation (end of P7):
- backend: ruff, format, mypy strict, pytest (341) — PASS; migration 2c4db9b939ad round-trip on roleradar_test
- frontend: prettier, lint, typecheck, test (52), build — PASS; pnpm test:e2e (19) — PASS
- Docker: rebuilt; dev DB upgraded only; worker runs roleradar.match_run

Exact next action (after human approval):
1. P8 application tracking: Application model/state machine (PRD §34 states), Apply action on the job page,
   pipeline table/Kanban, notes/dates/contacts/next action, Applied / Not applied job filters, dashboard tiles.
```

## P6 run

```text
Last updated: 2026-10-02
Last commit: see `git log -1`; pushed to origin/main with this phase
Current branch: main
Worktree: clean
Active phase: none — P0, P1, P3, P4, P2, P5, P6 complete
Status: STOPPED for human review

Completed this run:
- P6-001 backend: job status, ranked listing, outdated detection (591cc3d)
- P6-001..004 UI: jobs table, matches page, status actions, outdated notice, dashboard (this commit)

Validation (end of P6):
- backend: ruff, ruff format --check, mypy strict, pytest (316) — PASS
- migration 1818d540c7c5: round-trip on roleradar_test; dev DB upgraded only (982 companies, user's resume intact)
- frontend: prettier, lint, typecheck, test (48), build — PASS; pnpm test:e2e (18) — PASS

Exact next action (after human approval):
1. P7: bulk scoring ("score all unscored", sequential through Celery, relevance filter PRD §28 using profile target roles),
   SSE progress, retry classification (P7-004).
```

## P5 run

```text
Last updated: 2026-10-02
Last commit: see `git log -1`; pushed to origin/main with this phase
Current branch: main
Worktree: clean
Active phase: none — P0, P1, P3, P4, P2, P5 complete
Status: STOPPED for human review

Completed this run:
- P5-001/003 DecisionProvider + OpenJevProvider + /health/openjev (64a5ed8)
- P5-004 rubric_v1 + pure scoring (3bee949)
- P5-005/006 MatchScore, cache key, Celery/inline queue, /jobs/{id}/score, /matches (d6216f0)
- P5-007 Match Score panel + E2E with fake OpenJev (86f6944)
- docs: AGENTS/ARCHITECTURE matching flow (this commit)

Validation (end of P5):
- backend: ruff, ruff format --check, mypy strict, pytest (299) — PASS
- migration f8b28895d5f0: round-trip + alembic check on roleradar_test; dev DB upgraded only
- frontend: lint, typecheck, test (41), build — PASS; pnpm test:e2e (16) — PASS
- live: real OpenJev via Docker worker → DONE in 738 s, sensible result (see P5 phase exit); test data removed;
  user's resume ("Data Scientist", primary) untouched

Observations:
- OpenJev on the 24 GB Mac: ~40–50 s per question → ~10–13 min per job (15 questions). Fine for
  one-at-a-time scoring; P7 bulk matching must use the relevance filter (PRD §28) and run sequentially.
- Port 3100 is used by the Flenspay platform dev server; E2E now uses 3200/8200/4299.

Exact next action (after human approval):
1. P6: ranked Matches list (score sort, blocked jobs below unblocked by default with a toggle,
   filters), Jobs list Match column, job save/ignore status (PATCH /jobs/{id}), dashboard counts.
```

## P2 run

```text
Last updated: 2026-10-02
Last commit: see `git log -1` (P2-004); pushed to origin/main with this phase
Current branch: main
Worktree: clean
Active phase: none — P0, P1, P3, P4, P2 complete
Status: STOPPED for human review

Completed this run:
- docs: rubric_v1 decisions OD-2/3/4/6 (2432f62)
- P2-001 models (673043f), P2-002 storage + upload validation (f76b9fb),
  P2-003 extraction + /resumes API (d071ef3), P2-004 profile API + UI (this commit)

Validation (end of P2):
- backend: ruff, ruff format --check, mypy strict, pytest (244) — PASS
- migration 886b77401096: round-trip + alembic check on roleradar_test; dev DB upgraded only (982 companies intact)
- frontend: lint, typecheck, test (37), build — PASS
- pnpm test:e2e (15, isolated stack incl. resume upload flow + axe) — PASS
- Docker: rebuilt; upload → API container recreate → resume/profile/file intact → deleted via API (dev DB has 0 resumes)

Blocked / open:
- OD-1: confirm the OpenJev /v1/systemone contract against the main model card before P5 code.
- OpenJev latency ~45–50 s/request on the 24 GB Mac (15 GB model footprint); P5 must score asynchronously.

Exact next action (after human approval):
1. P5-001 DecisionProvider protocol + OpenJevProvider (httpx, timeouts, transport-only retries; not via SafeFetcher).
2. P5-004 rubric_v1 config (PRD §18/§19 decisions), P5-005 MatchScore model, P5-006 cache key.

Useful commands:
- ~/models/openjev/start-openjev.sh / stop-openjev.sh; curl http://127.0.0.1:4100/v1/version
- docker compose up -d; cd apps/api && uv run pytest; pnpm test && pnpm test:e2e

Important observations:
- Never run pytest with -W error::DeprecationWarning (PyMuPDF segfault; see AGENTS.md).
- Uploads: Docker volume `uploads` at /var/lib/roleradar/uploads; local runs use apps/api/uploads (git-ignored).
```

## P4 run

```text
Last updated: 2026-10-01
Last commit: see `git log -1` (P4-010); pushed to origin/main
Current branch: main (tracks origin/main; push after each phase per human decision)
Worktree: clean
Active phase: none — P0, P1, P3, P4 complete
Status: STOPPED for human review

Completed this run:
- P4-001 Job/JobSource models (77311fe), P4-002 SSRF fetcher + robots (a13c944),
  P4-003 connector protocol (d489b1d), P4-004 JSON-LD (89b5418), P4-008 generic (9b93073),
  P4-005..007 Greenhouse/Lever/Ashby (150ea80), P4-009 import service + API (a375c59),
  P4-010 UI (this commit)

Validation (end of P4):
- backend: ruff, ruff format --check, mypy strict, pytest (169) — PASS; alembic check on roleradar_test — no drift
- frontend: lint, typecheck, test (27), build — PASS
- pnpm test:e2e (11, isolated stack, axe on /, /companies, /eures, /jobs) — PASS
- live: Lever + Greenhouse URL import end-to-end on roleradar_test (created → unchanged), cleaned up
- docker compose up -d --build: all services healthy

Incident:
- P4-001: dev DB `roleradar` was accidentally downgraded (companies dropped) and reseeded;
  prior EURES progress lost. Prevention rules in AGENTS.md §7.

Blocked:
- P5 on PRD §83 OD-1..OD-4.

Exact next action (after human approval):
1. P2-001 Resume + CandidateProfile models (profile is manual entry, PRD §14).
2. P2-002 upload + secure storage, P2-003 text extraction, P2-004 profile UI.
```

## P3 run

```text
Last updated: 2026-10-01 (P4 run)
Previous run last commit: d4dd3ef (P3-002)
Current branch: main (local only; nothing pushed — origin/main does not exist yet)
Worktree: clean
Active phase: none — P0, P1, P3 complete; authorized scope finished
Active item: none
Status: STOPPED for human review (human authorized only P0, P1, P3)

Completed this run:
- META-001..003 docs (bb18c1a)
- P0-001 bootstrap (f7845b2)
- P1-001 Company model (d0a9428), P1-002 SIRI import (9a64b1b),
  P1-003 Companies API (d15e238), P1-004 Companies UI (9fc8b5f)
- P3-001 EURES backend (850fe2b), P3-002 EURES queue UI (d4dd3ef)

Validation (all run at the end of P3):
- backend: ruff check, ruff format --check, mypy strict, pytest (69) — PASS
- frontend: pnpm lint, typecheck, test (19), build — PASS
- pnpm test:e2e (8, isolated stack, incl. axe WCAG A/AA on /, /companies, /eures) — PASS
- docker compose up -d --build: all 5 services healthy; dev DB seeded (982, all NOT_CHECKED)

Blocked:
- P5 blocked on PRD §83 OD-1..OD-4 (OpenJev contract, must-have mapping, hard-blocker effect, display format).

Uncommitted files:
- none

Exact next action (after human approval):
1. P4-001: Job + JobSource models and migration (PRD §15 decisions).
2. P4-002: SSRF-safe fetcher (PRD §67 + ARCHITECTURE §6), then P4-003 connector protocol.
3. P4-010: wire "Import job URL" into the EURES queue rows and the current-company panel.

Useful commands:
- docker compose up -d postgres redis
- cd apps/api && uv run pytest
- pnpm test && pnpm test:e2e
- docker compose exec api python -m app.commands.import_siri /data/siri_certified_companies_eures_queue.xlsx

Important observations:
- Dev DB `roleradar` (host :5433) holds the real queue state. Tests use `roleradar_test`, E2E uses `roleradar_e2e`.
- Host port 5432 and 3001 are used by other projects on this machine.
- Next.js 16: read apps/web/node_modules/next/dist/docs before using unfamiliar APIs.
```
