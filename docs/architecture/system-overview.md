# System Overview — Career Compass AI

## What This Is

Career Compass AI is an enterprise, multi-tenant, AI-native career intelligence SaaS platform. It helps individuals build a living career profile and helps organizations run workforce development programs on top of that data, with AI assistance treated as a governed, first-class platform capability rather than a bolt-on feature.

## Architectural Style

**Modular monolith.** One deployable backend service, internally divided into modules with the same boundaries a microservice split would use:

```
API Layer
  ↓
Application Services   (use-case orchestration)
  ↓
Domain Services         (business rules, framework-free)
  ↓
Repository Interfaces   (ports)
  ↓
Infrastructure Adapters  (Postgres, Redis, S3, AI providers, IdPs)
```

Rationale is captured in `docs/adr/ADR-001-modular-monolith.md`. In short: one deployable unit keeps operational complexity low while we validate the product, and module boundaries are drawn so a future extraction to services is a deployment change, not a rewrite.

## Core Domains

- **Identity** — tenants, organizations, users, roles, permissions, sessions
- **Career Profile** — experience, education, certifications, goals
- **Resume Intelligence** — upload, parsing, extraction
- **Skill Intelligence** — free-text skill inventory (shared with Career
  Profile's Core Competencies) and target-role gap analysis (see ADR-005;
  no catalog/proficiency model)
- **Opportunity Intelligence** — job matching, career paths
- **Learning Intelligence** — learning paths, recommendations, progress
- **AI Career Coach** — conversational orchestration across the above
- **AI Platform** (cross-cutting) — provider abstraction, prompt/model registries, governance
- **Analytics** (cross-cutting) — engagement and adoption tracking
- **Audit** (cross-cutting) — immutable action log

## Multi-Tenancy

Shared database, shared schema, `tenant_id` ownership + PostgreSQL Row-Level Security, with a defined path to dedicated databases (Tier 2) and dedicated infrastructure (Tier 3) for larger or regulated customers. Full detail in `docs/architecture/multi-tenancy-design.md`.

## AI Governance

Every AI-generated artifact is traceable to the prompt version and model version that produced it, with token usage and confidence metadata retained for observability, evaluation, and human review. Full detail in `docs/architecture/ai-platform-architecture.md`.

## Phase 0 Scope

Phase 0 establishes the skeleton only: repository structure, configuration, logging, exception handling, health checks, the testing foundation, and the interface contracts (identity provider, LLM provider) that later phases implement against. No business entities, no database migrations beyond the empty baseline, and no AI provider calls yet — those begin in Phase 1 (Identity) and Phase 4 (AI Platform) respectively.

## Related Documents

- `docs/architecture/backend-architecture.md`
- `docs/architecture/frontend-architecture.md`
- `docs/architecture/ai-platform-architecture.md`
- `docs/architecture/multi-tenancy-design.md`
- `docs/architecture/security-architecture.md`
- `docs/adr/` — decision records
- `docs/runbooks/local-development.md`
