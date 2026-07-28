# ADR-002: PostgreSQL + Row-Level Security for Multi-Tenant Data Isolation

## Status
Accepted

## Context
The platform must support many tenants (organizations) with strict data isolation guarantees, while keeping operational cost and complexity manageable at launch. Options considered:

1. **Database-per-tenant** — strongest isolation, highest operational overhead (migrations, connections, backups multiply per tenant).
2. **Schema-per-tenant** — moderate isolation, still multiplies schema-migration operations per tenant.
3. **Shared schema + application-level filtering only** — lowest overhead, weakest isolation guarantee (a single missed `WHERE tenant_id = ...` clause leaks data).
4. **Shared schema + `tenant_id` + PostgreSQL Row-Level Security (RLS)** — shared operational simplicity of option 3, with database-enforced isolation that survives application-layer bugs.

## Decision
Adopt option 4 as the default (Tier 1), with an explicit, code-compatible upgrade path to dedicated databases (Tier 2) and dedicated infrastructure (Tier 3) for tenants that need it, detailed in `docs/architecture/multi-tenancy-design.md`.

Database driver: **psycopg 3** (async), ORM: **SQLAlchemy 2.0** (async engine), migrations: **Alembic only** — no manual schema changes, ever.

## Consequences
**Positive:**
- One database to operate at launch; RLS makes isolation a database guarantee, not just a code-review guarantee.
- Repository code is written once, scoped by `tenant_id`, and works unchanged whether a tenant is on Tier 1, 2, or 3 — the isolation tier is an infrastructure concern, not an application concern.
- Alembic gives a single, reviewable history of schema evolution.

**Negative / accepted trade-offs:**
- RLS policies must be added consistently for every new tenant-owned table — a missed policy is a real risk, mitigated by making it part of the standard migration template and a required code-review checklist item.
- Noisy-neighbor risk exists at Tier 1 (all tenants share database resources) — accepted for now, mitigated by the Tier 2 upgrade path for tenants that need dedicated performance.

## Revisit Trigger
Move a tenant to Tier 2 when it shows sustained resource contention or requires compliance-driven physical data separation; move to Tier 3 for regulated customers requiring dedicated infrastructure by contract.
