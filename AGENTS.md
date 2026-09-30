# AGENTS.md — RoleRadarAI Repository Map

> Product name: **RoleRadarAI**
>
> This file is intentionally concise. It is the map for coding agents, not the complete product specification.
>
> **Before doing any work, read `BACKLOG.md`.**

---

## 1. Sources of truth

Read in this order:

1. `docs/PRD.md` — product behavior and scope.
2. `docs/IMPLEMENTATION_PLAN.md` — phases, milestone order, acceptance criteria.
3. `docs/ARCHITECTURE.md` — technical architecture and provider boundaries.
4. `COMMIT_PROTOCOL.md` — autonomous work, testing, commit, and handoff contract.
5. `BACKLOG.md` — live execution state.

If a file does not yet exist, do not invent its contents. Use the approved repository docs that do exist and record the missing documentation in `BACKLOG.md`.

---

## 2. Session start

Before editing:

```bash
git status --short --branch
git log --oneline -12
```

Then read:

```text
AGENTS.md
BACKLOG.md
COMMIT_PROTOCOL.md
```

and the relevant PRD/implementation-plan section for the active backlog item.

Resume an `IN_PROGRESS` item before taking new work.

Never discard another agent's uncommitted changes blindly.

---

## 3. Approved stack

```text
Frontend     Next.js + TypeScript + App Router
Backend      Python + FastAPI
Database     PostgreSQL
Async        Redis + Celery
Workflow     LangGraph for stateful AI workflows only
Decision AI  OpenJev MLX 4-bit via DecisionProvider
Generation   Separate GenerationProvider
```

Runtime ports: web 3000, api 8000, postgres 5433 (host) → 5432, redis 6379, OpenJev 4000.

OpenJev runs **natively on the macOS host** (MLX needs Metal) and is never containerized. From inside Docker, use `http://host.docker.internal:4000`. See `docs/ARCHITECTURE.md`.

---

## 4. Core product pipeline

```text
SIRI certified companies
    ↓
EURES discovery workflow
    ↓
permitted original employer / ATS vacancy source
    ↓
normalized job
    ↓
resume comparison
    ↓
OpenJev dimension scores
    ↓
deterministic application scoring formula
    ↓
ranked jobs
    ↓
application tracking
    ↓
later LangGraph application pack
```

Do not collapse discovery, retrieval, scoring, and generation into one agent.

---

## 5. Permanent architecture boundaries

- Browser calls FastAPI, not model/provider APIs directly.
- Job sources use `JobSourceConnector` implementations.
- Decision models use `DecisionProvider`.
- Generative models use `GenerationProvider`.
- Application code owns final score weights.
- LangGraph orchestrates AI workflows; ordinary parsing/persistence/validation remains deterministic code.
- CVR values are strings and preserve source values exactly.
- The master resume is the candidate evidence source of truth.
- Generated material must not invent candidate experience.
- URL ingestion must include SSRF protection.
- RoleRadarAI never fetches EURES vacancy content; it only builds EURES search URLs (PRD §8).
- Company re-import never overwrites EURES workflow state (PRD §7.1).
- Product decisions live in `docs/PRD.md` §82; unresolved questions in §83. Do not invent answers to §83.
- Secrets never belong in the frontend or Git.

---

## 6. Expected repository shape

Prefer the approved structure if already present. Do not reorganize working code merely to match this suggestion.

```text
apps/
  web/                 # Next.js
  api/                 # FastAPI

docs/
  PRD.md
  IMPLEMENTATION_PLAN.md
  ARCHITECTURE.md
  exec-plans/
    active/
    completed/

data/
  siri_certified_companies_eures_queue.xlsx

AGENTS.md
BACKLOG.md
COMMIT_PROTOCOL.md
CLAUDE.md
```

---

## 7. Canonical commands

Frontend: pnpm workspace at the repo root (`apps/web`). Backend: uv project in `apps/api` (Python 3.13).

```bash
# infrastructure
cp .env.example .env                   # local only, never commit .env
docker compose up -d postgres redis    # Postgres on host port 5433, Redis on 6379
docker compose up -d --build           # full stack: web :3000, api :8000, worker

# frontend (run from repo root)
pnpm install
pnpm dev                               # http://localhost:3000
pnpm lint
pnpm typecheck                         # next typegen && tsc --noEmit
pnpm test                              # Vitest + React Testing Library (apps/web/tests/unit)
pnpm build
pnpm test:e2e                          # Playwright (apps/web/tests/e2e); needs API on :8000

# backend (run from apps/api)
uv sync
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "<message>"   # inspect the generated file
uv run uvicorn app.main:app --reload --port 8000
uv run celery -A app.workers.celery_app worker --loglevel=INFO
uv run ruff check . && uv run ruff format --check .
uv run mypy                            # strict
uv run pytest                          # uses Postgres db `roleradar_test` (auto-created, rebuilt from migrations)
```

Backend layout: `app/api/v1` (routers), `app/core` (config), `app/db` (engine/session/Base), `app/models` (ORM; import every model in `app/models/__init__.py`), `app/schemas` (Pydantic), `app/services` (business logic), `app/workers` (Celery), `migrations/` (Alembic).

Frontend layout: `app/` (routes), `components/` (shared UI), `features/<area>/` (feature components), `lib/api/` (typed fetch client + Zod schemas), `tests/unit`, `tests/e2e`.

Next.js is **v16**: read `apps/web/node_modules/next/dist/docs/` before using unfamiliar APIs (see `apps/web/AGENTS.md`). `params`/`searchParams` are async.

Never report a command as passing unless it was actually run.

---

## 8. Testing rules

Every completed backlog item requires applicable validation.

At minimum consider:

```text
frontend lint
frontend typecheck
frontend tests
frontend build
backend lint
backend tests
database migration verification
connector fixture tests
Playwright critical-flow tests
accessibility checks for changed interactive UI
```

A happy-path manual check alone is not completion.

---

## 9. Backlog discipline

`BACKLOG.md` is mandatory state.

Update it:

- when starting a task;
- when blocked;
- before a material commit;
- when completing a task;
- before ending a session.

Only mark `DONE` after verification and commit.

If a task is unclear and cannot safely proceed, mark it `BLOCKED` and continue with the next independent item.

---

## 10. Commit discipline

Follow `COMMIT_PROTOCOL.md`.

Expected message:

```text
<type>(<scope>): <summary> [<BACKLOG_ID>]
```

Example:

```text
feat(companies): import SIRI seed workbook [P1-002]
```

Before commit:

```bash
git status --short
git diff --check
git diff
```

Run applicable tests, update `BACKLOG.md`, and review for secrets.

Do not force-push, rewrite history, deploy, publish, send messages, or submit applications unless explicitly authorized.

---

## 11. Do not guess

Do not invent:

- hiring probability;
- sponsorship certainty;
- candidate qualifications;
- salaries;
- employer facts;
- job requirements;
- unapproved source/API access;
- undefined product behavior.

Unknown remains unknown.

---

## 12. Handoff rule

Before ending a run, ensure `BACKLOG.md` contains:

```text
last commit
active item
status
completed work
tests run
blockers
uncommitted changes
exact next action
```

A fresh agent with no chat history must be able to continue safely.
