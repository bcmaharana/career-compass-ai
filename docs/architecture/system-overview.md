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

## Career Intelligence Knowledge Graph (Architecture Approved, Not Yet Built)

A larger reference-data layer — canonical Skill/Role/Industry/
Technology/Certification/Company/CareerPath entities and their
relationships, additive alongside every domain above rather than
replacing any of them (Skill Intelligence's free-text model, ADR-005,
is explicitly unchanged). Proposed as **Phase 4.5**, starting point
**Phase 4.5.1**, landing between the existing Phase 4 (AI Platform) and
Phase 5 (Resume Intelligence) — see `cikg-mvp-roadmap.md`. Full
architecture (17 documents) written and approved across three review
rounds — the last of which added two ADRs (storage strategy, AI agent
execution boundary) and a concrete MVP 1 seed-data specification as
pre-coding actions. Implementation not yet started:

- `docs/adr/ADR-006-career-intelligence-knowledge-graph.md`,
  `ADR-007-cikg-storage-strategy.md`,
  `ADR-008-ai-agent-execution-boundary.md` — the decisions
- `docs/architecture/cikg-overview.md`, `cikg-ddd.md`, `cikg-knowledge-graph-model.md` — foundational pass
- `docs/architecture/cikg-content-governance.md` (incl. Edge Governance), `cikg-versioning-confidence.md` — how content is curated, trusted, and changes over time
- `docs/architecture/cikg-skill-ontology.md`, `cikg-career-levels.md`, `cikg-skill-evidence.md` — the skill/level/evidence models
- `docs/architecture/cikg-mvp1-seed-data.md` — the concrete 97-skill, 5-domain, 13-role starting dataset
- `docs/architecture/cikg-semantic-search.md` (incl. Knowledge Quality Score), `cikg-ai-agents.md`, `cikg-market-intelligence.md` — search, AI agents, labor-market data
- `docs/architecture/cikg-observability.md` — graph health metrics, incl. an ongoing profession-agnosticism check
- `docs/architecture/cikg-api-boundaries.md` — REST resource hierarchy and service ownership
- `docs/architecture/cikg-mvp-roadmap.md` — phased build order (starting at Phase 4.5.1) and exit criteria

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
