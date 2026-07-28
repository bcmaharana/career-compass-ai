# Runbook: Local Development Setup

## Prerequisites
- Docker + Docker Compose
- Python 3.12
- Node.js 20+ (once frontend lands in Phase 0.2)

## Backend Setup

```bash
cd backend
cp .env.example .env          # fill in local values; never commit .env
python3.12 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Start Infrastructure Services

```bash
cd infra
docker compose up -d postgres redis minio
```

This brings up:
- **postgres** — pgvector-enabled Postgres, port 5432
- **redis** — port 6379
- **minio** — S3-compatible local object storage, ports 9000 (API) / 9001 (console)

## Run the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

- Health check: `GET http://localhost:8000/api/v1/health`
- OpenAPI docs: `http://localhost:8000/docs`

## Database Migrations

```bash
cd backend
alembic upgrade head             # apply migrations
alembic revision --autogenerate -m "description"  # create a new migration (always review the diff — never hand-write schema)
```

## Seed Platform Defaults

Phase 1 onward, run this once against a fresh database before registering
the first tenant — it seeds the global (`tenant_id = NULL`) permissions
and roles (`platform_admin`, `organization_admin`, `manager`,
`career_coach`, `employee`, `ai_service_account`) that tenant registration
and RBAC enforcement depend on:

```bash
cd backend
python scripts/seed_platform_defaults.py
```

Idempotent — safe to re-run; it only inserts rows that don't already exist.

## Test Database

Integration tests (`tests/integration/`) run against a **dedicated test
database**, never the local dev database — configured via
`backend/.env.test`, loaded automatically by `tests/conftest.py` before
any app module is imported. One-time setup:

```sql
-- via psql, as a superuser:
CREATE DATABASE career_compass_test OWNER compass;
```

The test suite applies migrations and seeds platform defaults
automatically (see `conftest.apply_migrations_and_seed`, session-scoped)
— no manual `alembic upgrade` needed against the test database.

## Run Tests

```bash
cd backend
pytest                          # all tests
pytest tests/unit                # fast, no infra required
pytest tests/integration         # requires the career_compass_test database (see above)
pytest --cov=app                 # with coverage
```

## Common Issues

- **`psycopg` connection errors on start:** confirm `docker compose ps` shows `postgres` healthy before starting the backend; the container needs a few seconds after `up -d`.
- **Port conflicts:** if 5432/6379/9000 are already in use locally, override them in `infra/docker-compose.override.yml` rather than editing the base file.
- **Python version drift:** this project pins Python 3.12 intentionally (see ADR discussion in `docs/architecture/backend-architecture.md`) — 3.13/3.14 are not yet validated against all dependencies (notably database driver wheels), so use 3.12 for local development until that's revisited.
- **Integration tests fail with a database error mentioning `career_compass` (not `_test`):** `.env.test` didn't load before `app.adapters.db.base` created its engine — check that `tests/conftest.py`'s `load_dotenv` call is still at the very top of the file, above the `from app.main import app` line. This ordering is load-bearing, not stylistic (see the comment in that file).
