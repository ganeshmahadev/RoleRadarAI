# RoleRadarAI

A personal job-discovery copilot for companies certified under Denmark's SIRI Fast-track scheme. It keeps the 982-company SIRI list as the company universe, makes EURES a mandatory, human-driven discovery step, imports vacancies from their original employer or ATS source, and later scores them against your resume with OpenJev.

- Product: [`docs/PRD.md`](docs/PRD.md) · Phases: [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) · Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Agent workflow: [`AGENTS.md`](AGENTS.md), [`BACKLOG.md`](BACKLOG.md), [`COMMIT_PROTOCOL.md`](COMMIT_PROTOCOL.md)

## Requirements

Docker Desktop, Node 22 + pnpm, [uv](https://docs.astral.sh/uv/) (Python 3.13 is installed automatically). OpenJev (P5+) runs natively on an Apple Silicon Mac with MLX on port 4000. It is not part of Docker.

## Run everything in Docker

```bash
cp .env.example .env
docker compose up -d --build          # web :3000, api :8000, postgres :5433, redis :6379, worker
open http://localhost:3000
```

## Run natively (faster iteration)

```bash
docker compose up -d postgres redis
cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000
pnpm install && pnpm dev               # from the repo root, web on :3000
cd apps/api && uv run celery -A app.workers.celery_app worker --loglevel=INFO   # optional
```

## Checks

```bash
# frontend (repo root)
pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm test:e2e                          # needs the API running

# backend (apps/api; needs `docker compose up -d postgres redis`)
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```
