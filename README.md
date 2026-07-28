# Career Compass AI

Enterprise, multi-tenant, AI-native career intelligence SaaS platform.

**Status:** Phase 0.1 — repository initialization and backend foundation.

## Start Here

- `docs/architecture/system-overview.md` — what this is and how it's structured
- `docs/adr/` — why key decisions were made
- `docs/runbooks/local-development.md` — how to run this locally

## Structure

```
backend/    FastAPI modular monolith (Phase 0 foundation implemented)
frontend/   React + TypeScript (Phase 0.2 — not yet scaffolded)
infra/      Docker Compose for local infrastructure
docs/       Architecture docs, ADRs, runbooks
```

## Quickstart

```bash
cd infra && docker compose up -d postgres redis minio
cd ../backend
cp .env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` or `http://localhost:8000/api/v1/health`.

See `docs/runbooks/local-development.md` for full detail and troubleshooting.
