# RoleRadarAI — Architecture

> Summary of the approved architecture. The full detail is in `docs/PRD.md` §9–§13, §29, §35, §67 and §73. If this file and the PRD disagree, the PRD wins.

## 1. Runtime topology

```text
┌──────────────────── macOS host ─────────────────────────────────────────┐
│                                                                          │
│  Browser ──► Next.js web (:3000) ──(browser fetch, CORS)──► FastAPI (:8000)
│                                                               │     │    │
│                                                     Postgres (:5433)│    │
│                                                     Redis (:6379) ◄─┘    │
│                                                       ▲                  │
│                                                  Celery worker           │
│                                                                          │
│  OpenJev MLX server (:4100, native, Metal GPU)  ◄── DecisionProvider     │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Docker Compose** runs `postgres`, `redis`, `api`, `worker` and `web`.
- **OpenJev never runs in Docker.** MLX needs Apple's Metal GPU, and Docker on macOS runs Linux containers in a VM without Metal access. It runs natively on the host on port 4100.
- The API reaches OpenJev at `OPENJEV_BASE_URL`: `http://localhost:4100` when the API runs on the host, `http://host.docker.internal:4100` when it runs in Compose.
- Start/stop OpenJev with `~/models/openjev/start-openjev.sh` / `stop-openjev.sh` (README command with `--port 4100`, bound to 127.0.0.1; Docker Desktop still reaches it via `host.docker.internal`). It needs ~14 GB of unified memory: on a 24 GB Mac, keep the Docker VM allotment small and close heavy apps, or requests slow from ~seconds to ~a minute because of swapping (measured 2026-10-01).
- The API and web app can also run natively (with Postgres and Redis in Compose) for faster iteration. The commands are in `AGENTS.md`.

| Service | Port (host) | Runs in |
|---|---|---|
| web (Next.js) | 3000 | Compose or host |
| api (FastAPI) | 8000 | Compose or host |
| postgres | 5433 → 5432 | Compose |
| redis | 6379 | Compose |
| worker (Celery) | — | Compose or host |
| OpenJev | 4100 | host only (MLX) |

## 2. Service boundaries

- The browser talks only to FastAPI (`/api/v1`). It never talks to models, providers or the database.
- FastAPI services: Company, EURES workflow, Resume, Job, Source Connector, Match, Application, and LangGraph later.
- Long-running work (URL import in bulk, scoring, agent runs) goes through Celery via Redis (PRD §10, §44).
- Deterministic code owns import, parsing, normalization, deduplication, hashing, the scoring formula and persistence. LangGraph is used only for stateful AI workflows (PRD §35).

## 3. Provider boundaries (PRD §73)

```text
CompanySource        SIRI workbook importer (P1); live SIRI refresh later
JobSourceConnector   EuresDiscoveryConnector (URL building only), JSON-LD, Greenhouse, Lever, Ashby, generic HTML
DecisionProvider     OpenJevProvider (P5)
GenerationProvider   configured later (P9)
ResumeParser         PDF / DOCX / TXT (P2)
EmbeddingProvider    optional, later
StorageProvider      local upload dir (P2)
```

`JobSourceConnector` adds `can_handle_url` and `fetch_job_by_url` for URL import (PRD §9).

## 4. Data entities

| Entity | Phase | Key rules |
|---|---|---|
| Company | P1 | `UNIQUE(cvr)`; CVR is TEXT, preserved exactly; re-import never overwrites EURES state (PRD §7.1) |
| EURES workflow fields on Company | P1 schema, P3 behavior | status transitions in PRD §8 |
| Job, JobSource | P4 | nullable `company_id`; one canonical Job, many sources; changed content creates a snapshot (PRD §15) |
| Resume, CandidateProfile | P2 | profile entered manually; resume text is the source of evidence |
| MatchScore | P5 | stores dimensions, model, revision, rubric version and input hash (PRD §16) |
| Application | P8 | references the exact resume, job and artifacts |

## 5. EURES boundary

RoleRadarAI **never** fetches or extracts EURES vacancy content (PRD §8). It only builds search URLs, which the user opens in their own browser, and records the workflow status. The job importer rejects EURES hosts.

## 6. Security boundaries (PRD §67)

- URL importer: http/https only. It blocks localhost, loopback, RFC1918, link-local, metadata endpoints, `file://` and `ftp://`. It resolves DNS once and connects to the validated IP, re-validates every redirect hop, and enforces bounded size and timeout.
- The OpenJev client is a separate, configured internal client and does not go through the SSRF-guarded fetcher.
- Uploads live outside public directories, with MIME types validated and filenames sanitized.
- Secrets come only from environment variables. `.env` is never committed. The full resume text is never logged by default.
