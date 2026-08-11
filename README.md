# Career Compass AI

An enterprise, multi-tenant, AI-native career intelligence platform. Individuals build a
living career profile; organizations run workforce development on top of it; AI is a
governed platform capability — with explainability, audit logging, and human-review
controls built in from the start — not a bolted-on chatbot.

## What's built

- **Identity & multi-tenancy** — JWT auth (sliding-session refresh), phone login (Firebase,
  Personal and Enterprise accounts), password reset, email-verified self-serve signup
  (Personal, no-organization accounts and Enterprise/team accounts), real account deletion,
  RBAC, and row-level multi-tenant isolation enforced at the Postgres level (not just in
  application code)
- **Career Profile** — experience, education, certifications, career goals, highlights,
  achievements, peer endorsements, core competencies — full CRUD with manual reordering
- **Resume Intelligence** — upload a resume (PDF/DOCX), LLM-extracted structured data,
  review-and-accept before anything merges into your profile, full resume history
- **Skill Intelligence** — skill inventory plus target-role gap analysis
- **Career Intelligence Knowledge Graph (CIKG)** — a governed skills/roles/competencies
  graph (hybrid full-text + vector + graph search) backing skill-gap analysis, with a
  full draft → review → approve content-governance workflow
- **AI Career Coach** — conversational coaching grounded in your actual profile and gap
  analysis, with pluggable model providers (Anthropic, Groq, or a self-hosted Ollama model)
  selectable per user
- **Terms of Service & Privacy Policy** — required, recorded consent at signup

See `CLAUDE.md` for the full, detailed build history and architectural decisions behind
all of the above.

## Tech stack

- **Backend**: Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16
  (pgvector), Redis, MinIO (S3-compatible object storage)
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand,
  React Router
- **Infra**: Docker Compose (dev and prod), self-hostable

## Architecture

A modular monolith with strict layering:

```
API (routers) → Application Services → Domain Services → Repository Interfaces → Adapters
```

- `app/api/` — thin routers only, zero business logic
- `app/application/` — use-case orchestration
- `app/domain/` — pure business logic, framework-free (unit-testable without a database)
- `app/adapters/` — the only place SQLAlchemy, boto3, or any infra SDK is imported

Full rationale in `docs/adr/` and `docs/architecture/`.

## Getting started

Requires Docker Desktop. On Windows, the fastest path:

```powershell
git clone https://github.com/bcmaharana/carreer-compass-ai.git
cd carreer-compass-ai
.\start-dev.ps1
```

This brings up Postgres/Redis/MinIO/the backend via Docker, applies migrations and seeds
platform defaults, and launches the frontend dev server. Then visit:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`

Run `.\sync-dependencies.ps1` whenever `pyproject.toml` or `package.json` gains a new
dependency. See `docs/runbooks/local-development.md` for full setup detail and
troubleshooting, and `backend/.env.example` / `frontend/.env.example` for required
environment variables.

## Project structure

```
backend/    FastAPI backend — domain, application, adapters, API layers
frontend/   React + TypeScript frontend
infra/      Docker Compose (dev and prod) + Postgres role/RLS setup
docs/       Architecture docs, ADRs, runbooks
```

## Documentation

- `docs/architecture/system-overview.md` — what this is and how it's structured
- `docs/adr/` — why key architectural decisions were made
- `docs/runbooks/` — operational how-tos (local dev, deployment)
- `CLAUDE.md` — detailed build history, conventions, and known gotchas
