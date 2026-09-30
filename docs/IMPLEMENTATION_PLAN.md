# RoleRadarAI — Implementation Plan

> Source: phase and milestone sections moved from the original plan (`plan.md`), keeping their section numbers. Product behavior lives in `docs/PRD.md`; architecture in `docs/ARCHITECTURE.md`.

## Execution order (Decision 2026-10-01)

The human asked for a working discovery slice before the resume and AI work:

```text
Next.js → FastAPI → Postgres → import 982-company workbook → Companies UI → EURES queue → original-job URL importer
```

So phases run in this order (phase IDs are kept for traceability):

```text
P0  Repository bootstrap
P1  SIRI company foundation
P3  EURES discovery workflow        (without job import; see §53)
P4  Job-source connectors            (adds Import job URL to the EURES queue)
P2  Resume foundation
P5  OpenJev integration              (blocked on PRD §83 OD-1..OD-4)
P6  Ranked matching
P7  Bulk processing
P8  Application tracking
P9  Generation provider
P10 LangGraph application pack
P11 AI workspace
P12 Feedback learning
P13 Authorized EURES (deferred)
```

P3 does not depend on P2. P4 does not depend on P2; the relevance filter (PRD §28) needs the P2 profile and is added when P2 lands.

## Stop points

After each phase: run the full relevant suite, update `BACKLOG.md`, commit, and report. Current authorization: **P0, P1, P3**, then stop for review.

---

# 50. Phase 0 — Repository Bootstrap

## Objective

Produce a runnable development environment.

## Tasks

Create monorepo.

Create:

```text
Next.js application
FastAPI application
PostgreSQL
Redis
Celery worker
Docker Compose
```

Configure:

```text
ESLint
Prettier
pytest
ruff
mypy
Alembic
```

Add:

```text
.env.example
```

Required environment variables:

```text
DATABASE_URL=
REDIS_URL=

OPENJEV_BASE_URL=http://localhost:4000   # host.docker.internal:4000 from inside Docker
OPENJEV_MODEL=openjev/openjev-MLX-4bit

UPLOAD_DIR=
APP_ENV=development

GENERATION_PROVIDER=
GENERATION_API_KEY=
```

## Acceptance criteria

```text
docker compose up
```

starts:

```text
web
api
postgres
redis
worker
```

OpenJev runs separately and natively on the Apple host (MLX, port 4000). It is not part of Docker Compose.

Health endpoint returns 200.

Ports (Decision 2026-10-01):

```text
web       3000
api       8000
postgres  5433 on host → 5432 in container (5432 is already used on the dev machine)
redis     6379
openjev   4000 (host, native MLX)
```

---

# 51. Phase 1 — SIRI Company Foundation

## Objective

Load the existing workbook into PostgreSQL.

## Tasks

Implement:

```text
Company model
Alembic migration
Excel importer
normalization service
deduplication
company API
Companies UI
```

Input:

```text
siri_certified_companies_eures_queue.xlsx
```

CVR must remain text.

## Acceptance criteria

All 982 rows import.

No duplicate CVR rows.

Company names match the workbook.

Company search works.

Filters work.

EURES URL is available for every company.

The generated EURES URL equals the workbook URL for all 982 companies.

The two non-8-character CVRs (`423380281`, `8485085`) are preserved exactly.

Re-running the import creates no duplicates and does not overwrite EURES state (PRD §7.1).

Companies UI scope in P1 follows PRD §23 "Phase availability": no job/relevance columns or placeholder actions.

---

# 52. Phase 2 — Resume Foundation

## Objective

Create canonical user profile.

## Tasks

Implement:

```text
Resume model
file upload
PDF parsing
DOCX parsing
raw text viewer
candidate profile
profile editing
primary resume
```

## Acceptance criteria

User uploads PDF.

Text extraction succeeds.

User can view extracted content.

User can edit structured profile.

Resume survives restart.

---

# 53. Phase 3 — EURES Discovery Workflow

## Objective

Make EURES a usable part of daily company scanning.

## Tasks

Build `/eures`.

Show:

```text
company
CVR
status
last checked
jobs found
search action
```

Button:

```text
Open EURES Search
```

uses the generated URL.

Provide actions:

```text
Mark No Relevant Jobs   (= Mark Checked / Mark complete, PRD §8)
Mark Error
Reset
Add Notes
Next unchecked
```

"Import Original Job URL" moves to P4 (Decision 2026-10-01): P3 runs before P4 and placeholder buttons are not allowed. The "jobs found" column also arrives in P4.

Persist progress. Status transitions follow PRD §8.

## Acceptance criteria

User can start with company 1.

Open its EURES search (status becomes `OPENED`).

Return to RoleRadarAI.

Mark the company completed (`CHECKED_NO_JOBS`).

Continue to the next unchecked company.

Refresh browser.

State remains unchanged.

Counters show total / checked / remaining.

---

# 54. Phase 4 — Job Source Connectors

## Objective

Turn vacancy URLs into normalized jobs.

## Initial connectors

Implement:

```text
Generic HTML
JSON-LD JobPosting
Greenhouse
Lever
Ashby
```

Add new connectors only when necessary.

## Connector tests

Every connector requires fixtures.

Never write tests against a live production careers site.

Store sanitized HTML/JSON fixtures under:

```text
tests/fixtures/jobs/
```

## Acceptance criteria

A supported employer URL produces:

```text
title
company
description
location
apply URL
source
```

Duplicate imports produce one canonical job.

From an EURES queue row, "Import Original Job URL" imports a vacancy linked to that company, and the company becomes `JOB_FOUND` (completes the P3 flow).

EURES URLs are rejected; `robots.txt` disallow falls back to manual paste (PRD §26).

Re-importing a URL with changed content creates a snapshot, not an overwrite (PRD §15).

---

# 55. Phase 5 — OpenJev Integration

## Objective

Score vacancy/resume fit.

## Tasks

Implement:

```text
DecisionProvider interface
OpenJev provider
health check
input builder
rubric_v1
response validation
match persistence
input hashing
result caching
```

## Acceptance criteria

Selecting:

```text
Score Job
```

produces all required dimensions.

Result survives restart.

Rescoring identical input uses cache.

Changing the resume invalidates cache.

Changing JD invalidates cache.

Changing rubric version invalidates cache.

---

# 56. Phase 6 — Ranked Matching Experience

## Objective

Make the product useful for daily job search.

## Build

Dashboard.

Jobs table.

Matches table.

Job details.

Filters.

Sorting.

Saved jobs.

Ignored jobs.

## Acceptance criteria

User can answer:

```text
"What are the 20 strongest jobs I've found?"
```

within one screen.

---

# 57. Phase 7 — Bulk Processing

## Objective

Process multiple imported jobs without blocking FastAPI.

Implement:

```text
Celery tasks
Redis queue
task status
retry policy
SSE progress
batch matching
```

Do not retry:

```text
invalid URLs
404
unsupported source
validation errors
```

Retry:

```text
network timeout
temporary 5xx
OpenJev unavailable
```

Use bounded exponential backoff.

---

# 58. Phase 8 — Application Tracking

Implement Kanban or table:

```text
Saved
Preparing
Applied
Interview
Offer
Rejected
```

Add:

```text
notes
dates
contacts
next action
```

Application entries must reference:

```text
exact resume version
exact job
exact generated artifacts
```

---

# 59. Phase 9 — Generative AI Provider

Add:

```text
GenerationProvider
```

Do not hardwire provider calls throughout business logic.

Add prompt versions.

Persist:

```text
provider
model
prompt version
input hash
output
created_at
```

---

# 60. Phase 10 — LangGraph Application Pack

Build:

```text
ContextBuilder
ResumeTailorNode
CoverLetterNode
OutreachNode
InterviewPrepNode
FactCheckerNode
HumanApprovalNode
```

Use a persistent LangGraph checkpointer.

LangGraph's checkpointing is specifically designed to preserve graph state across steps and enable durable execution and human review.

---

# 61. Phase 11 — AI Workspace UI

Route:

```text
/workspace/[jobId]
```

Tabs:

```text
Overview
Resume
Cover Letter
LinkedIn
Email
Interview
```

Example:

```text
┌─────────────────────────────────────────────────────────────┐
│ AI Engineer — Company X                         Match 88    │
├─────────────────────────────────────────────────────────────┤
│ Overview | Resume | Cover Letter | LinkedIn | Email        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Generated content                                           │
│                                                             │
│ [Regenerate] [Edit] [Copy] [Save Version]                  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Evidence                                                     │
│ ✓ supported by resume                                      │
│ △ needs review                                              │
└─────────────────────────────────────────────────────────────┘
```

---

# 62. Phase 12 — Feedback Learning

Add buttons to each recommendation:

```text
Good recommendation
Bad recommendation
Applied
Would never apply
```

Store:

```text
job_id
resume_id
score
user_decision
reason
```

This creates the **real personalized dataset**.

After several hundred labels, evaluate whether fine-tuning is useful.

Do not fine-tune before collecting reliable personalized evaluation data.

---

# 63. Phase 13 — Authorized EURES Integration

If EURES partner/API access or explicit authorization becomes available:

Implement:

```text
EuresAuthorizedConnector
```

against the same `JobSourceConnector` protocol.

Replace:

```text
human discovery
```

with:

```text
scheduled company discovery
```

without changing:

```text
database
UI
matching
OpenJev
LangGraph
applications
```

This separation is mandatory.

---

# 71. Codex Build Instructions

Codex should implement the application **phase-by-phase**.

Do not attempt all features simultaneously.

For every phase:

```text
1. Read PRD.
2. Inspect current repository.
3. Implement only the current phase.
4. Add/update database migration.
5. Add tests.
6. Run backend tests.
7. Run frontend tests.
8. Run lint/typecheck.
9. Update README.
10. Do not break previous phases.
```

Do not:

```text
replace existing working code unnecessarily
invent new infrastructure without need
hardcode secrets
hardcode model outputs
duplicate schemas between layers without reason
mix retrieval logic with scoring logic
mix generative AI with decision-model logic
```

---

# 74. First Development Milestone

The first milestone Codex should deliver is deliberately small:

```text
Next.js
    ↓
Companies page
    ↓
FastAPI
    ↓
PostgreSQL
    ↓
SIRI workbook import
    ↓
982 companies visible
    ↓
EURES search button works
```

Do **not** integrate OpenJev before this works.

---

# 75. Second Development Milestone

```text
Resume upload
    +
Job URL import
    +
Normalized Job record
```

Confirm those independently before introducing AI.

---

# 76. Third Development Milestone

```text
Resume
+
Job
 ↓
OpenJev
 ↓
Dimension scores
 ↓
Python scoring formula
 ↓
Match screen
```

At this point the MVP has its fundamental intelligence.

---

# 77. Fourth Development Milestone

```text
EURES workflow
+
jobs
+
ranked matches
+
application tracking
```

This becomes the version used every day.

---

# 78. Fifth Development Milestone

Only then add:

```text
LangGraph
+
generative model
+
application pack
```

---
