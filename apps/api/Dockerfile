FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# git is needed only to fetch python-jobspy from GitHub (pinned commit; the PyPI release
# breaks on Python 3.13), so it is removed again in the same layer.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && uv sync --frozen --no-dev --no-install-project \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
# Uploaded resumes live here (Docker named volume), outside any web-served directory.
RUN useradd --create-home app && chown -R app /app \
    && mkdir -p /var/lib/roleradar/uploads && chown -R app /var/lib/roleradar && chmod 700 /var/lib/roleradar/uploads
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
