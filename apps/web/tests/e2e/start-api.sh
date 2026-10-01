#!/usr/bin/env sh
# Isolated API for Playwright: its own database (roleradar_e2e), rebuilt and seeded
# on every run, so E2E tests never touch the development database.
set -eu
cd "$(dirname "$0")/../../../api"

export DATABASE_URL="${E2E_DATABASE_URL:-postgresql+psycopg://roleradar:roleradar@localhost:5433/roleradar_e2e}"
export REDIS_URL="${E2E_REDIS_URL:-redis://localhost:6379/14}"
export CORS_ORIGINS='["http://localhost:3100"]'
export UPLOAD_DIR="$(mktemp -d -t roleradar-e2e-uploads)"   # never the real upload folder

uv run python - <<'PY'
import os
import psycopg
from sqlalchemy import make_url

url = make_url(os.environ["DATABASE_URL"])
admin = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
with psycopg.connect(admin, autocommit=True) as conn:
    if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
        conn.execute(f'CREATE DATABASE "{url.database}"')
PY
uv run alembic downgrade base >/dev/null 2>&1
uv run alembic upgrade head
uv run python -m app.commands.import_siri ../../data/siri_certified_companies_eures_queue.xlsx
exec uv run uvicorn app.main:app --port 8100 --log-level warning
