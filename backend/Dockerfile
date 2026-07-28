# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps needed to build psycopg[binary] wheels on some platforms
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Source is copied *before* `pip install .` deliberately — pyproject.toml
# declares the local `app` package via setuptools' package discovery
# (`include = ["app*"]`), so installing before the source exists means
# pip resolves and installs every third-party dependency correctly but
# silently installs zero local packages (nothing to find yet). That
# mismatch didn't surface via `uvicorn app.main:app` (uvicorn adds the
# working directory to the import path itself) but broke immediately
# for `python scripts/seed_platform_defaults.py` (a plain script
# invocation only adds the script's own directory, not the working
# directory) — caught by actually running the seed script against a
# fresh container, not by reasoning about the Dockerfile alone.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
