# BACKLOG.md — RoleRadarAI Execution State

> This file is the persistent work queue for autonomous Codex/Claude sessions.
>
> **Agents: update this file continuously. Do not rely on conversation memory.**
>
> Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `VERIFYING`, `DONE`, `DEFERRED`.

---

## Current state

```text
Active phase: P3 complete (P0, P1, P3 done) — STOPPED for human review
Active item: none (next: P4-001, needs human go-ahead)
Last known-good commit: P3-002 (see Overnight handoff)
Current branch: main
Worktree: clean after P0 commit
Last updated: 2026-10-01
```

## Phase order and authorization

Order (human decision 2026-10-01): **P0 → P1 → P3 → P4 → P2 → P5 → P6 …**

Reason: the human asked for the vertical discovery slice (Next.js → FastAPI → Postgres → workbook import → Companies UI → EURES queue → original-job URL importer) before the resume and OpenJev work. P3 runs before P4, so the EURES queue's "Import job URL" action moved to P4-010.

Authorized in the current run: **P0, P1, P3**, then stop for human review.

Decisions: `docs/PRD.md` §82. Open decisions (do not guess): `docs/PRD.md` §83 (OD-1..OD-5; OD-1..OD-4 block P5).

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

- OpenJev is not part of Compose (native MLX on host, port 4000).
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

**Status:** TODO  
**Depends on:** P1 phase exit

### Acceptance criteria

- [ ] Resume model;
- [ ] CandidateProfile model;
- [ ] migrations;
- [ ] primary-resume semantics;
- [ ] tests.

---

## P2-002 — Implement resume upload and secure storage

**Status:** TODO  
**Depends on:** P2-001

### Acceptance criteria

- [ ] PDF;
- [ ] DOCX;
- [ ] TXT;
- [ ] MIME validation;
- [ ] file-size limits;
- [ ] filenames sanitized;
- [ ] files outside public web directories;
- [ ] tests.

---

## P2-003 — Extract resume text

**Status:** TODO  
**Depends on:** P2-002

### Acceptance criteria

- [ ] PDF extraction;
- [ ] DOCX extraction;
- [ ] normalized text;
- [ ] content hash;
- [ ] extraction errors surfaced cleanly;
- [ ] tests.

---

## P2-004 — Candidate profile review/edit UI

**Status:** TODO  
**Depends on:** P2-003

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

**Status:** TODO

---

## P4-002 — Add URL-import security layer

**Status:** TODO  
**Priority:** P0

### Mandatory

- [ ] HTTP/HTTPS only;
- [ ] DNS/IP validation;
- [ ] block localhost;
- [ ] block private/link-local networks;
- [ ] block metadata endpoints;
- [ ] validate redirects;
- [ ] bounded response sizes/timeouts;
- [ ] tests.

---

## P4-003 — Implement `JobSourceConnector` abstraction

**Status:** TODO  
**Depends on:** P4-001, P4-002

---

## P4-004 — Implement JSON-LD `JobPosting` connector

**Status:** TODO  
**Depends on:** P4-003

---

## P4-005 — Implement Greenhouse connector

**Status:** TODO  
**Depends on:** P4-003

---

## P4-006 — Implement Lever connector

**Status:** TODO  
**Depends on:** P4-003

---

## P4-007 — Implement Ashby connector

**Status:** TODO  
**Depends on:** P4-003

---

## P4-008 — Implement generic permitted job-page fallback

**Status:** TODO  
**Depends on:** P4-003

Use deterministic fixtures in tests.

---

## P4-009 — Implement job normalization/deduplication

**Status:** TODO

### Dedup inputs

```text
normalized company
normalized title
location
content hash
```

---

## P4-010 — Import job URL from the EURES queue

**Status:** TODO  
**Depends on:** P3-002, P4-003..P4-009

### Acceptance criteria

- [ ] "Import job URL" action on each EURES queue row;
- [ ] imported job linked to that company;
- [ ] company becomes `JOB_FOUND`;
- [ ] Jobs found column + Has jobs filter on Companies/EURES;
- [ ] Playwright flow: open EURES → import → next unchecked.

---

# Phase P5 — OpenJev matching

**Blocked on:** `docs/PRD.md` §83 OD-1..OD-4.

## P5-001 — Define `DecisionProvider`

**Status:** TODO

---

## P5-002 — Run/configure OpenJev local service

**Status:** TODO

Expected local endpoint:

```text
http://localhost:3000/v1/systemone
```

Do not commit model weights into Git.

---

## P5-003 — Implement `OpenJevProvider`

**Status:** TODO  
**Depends on:** P5-001, P5-002

---

## P5-004 — Define rubric v1

**Status:** TODO

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

**Status:** TODO

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

**Status:** TODO

Cache key must change when:

```text
resume changes
job content changes
model revision changes
rubric version changes
```

---

# Phase P6 — Ranked matching experience

## P6-001 — Build Jobs list

**Status:** TODO

---

## P6-002 — Build Matches list

**Status:** TODO

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

## P6-003 — Build Job detail / evidence screen

**Status:** TODO

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

## P7-001 — Add Celery task framework

**Status:** TODO

---

## P7-002 — Add match-run queue

**Status:** TODO

---

## P7-003 — Add SSE progress updates

**Status:** TODO

---

## P7-004 — Add retry classification

**Status:** TODO

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

```text
Last updated: 2026-10-01
Last commit: d4dd3ef (P3-002)
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
