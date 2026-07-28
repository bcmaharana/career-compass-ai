# Multi-Tenancy Design — Career Compass AI

## Model

Shared database, shared schema, `tenant_id` column on every tenant-owned table, enforced by **PostgreSQL Row-Level Security (RLS)** in addition to application-level filtering (defense in depth — an application bug that forgets a `WHERE tenant_id = ...` clause still cannot leak rows, because the database itself won't return them).

## Tenant Resolution

1. Client authenticates; JWT access token carries a `tenant_id` claim.
2. Request-scoped middleware (`app/api/middleware/request_context.py`) extracts and validates `tenant_id` from the token.
3. Middleware issues `SET LOCAL app.tenant_id = '<uuid>'` on the request's database session/transaction.
4. RLS policies on every tenant-owned table reference `current_setting('app.tenant_id')`, so every query in that transaction is automatically scoped.

## Tier Roadmap

| Tier | Isolation | Target customer | Migration cost |
|---|---|---|---|
| Tier 1 (default, Phase 1 onward) | Shared DB + shared schema + RLS | Most tenants | — |
| Tier 2 | Shared schema, dedicated database | Large enterprise tenants needing performance/compliance isolation | Connection-string swap per tenant; repository code unchanged since it already scopes by `tenant_id` |
| Tier 3 | Dedicated infrastructure (own deployment) | Regulated customers | Same container image, isolated deployment; no application code change |

The repository and domain layers are written against a `tenant_id`-scoped interface regardless of tier, so upgrading a tenant's isolation tier is an infrastructure/ops change, not a code change.

## What's Exempt from Tenant Scoping

Global reference/catalog data is intentionally **not** tenant-owned:

- `PromptVersion`, `ModelVersion` — platform-managed AI governance registries
- Platform-wide `JobOpportunity`/`LearningPath` catalog entries (tenant-specific ones still carry `tenant_id`)

These tables are explicitly marked as exceptions in the schema and migration comments so a future contributor doesn't assume every table needs RLS.

## Phase 0 Status

Phase 0 does not yet create any tenant-owned tables (no entities exist yet). This document defines the pattern that Phase 1's `Tenant`, `Organization`, and `User` migrations will implement, including the RLS policy template, so Phase 1 can move quickly against an agreed design rather than re-litigating it.

## RLS Policy Template (for Phase 1 implementation)

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON <table_name>
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

Applied via Alembic migration alongside each tenant-owned table's creation — never applied manually outside of migrations.

**Three details verified by hand-testing against a real Postgres instance while building Phase 1, not just by inspecting the SQL:**

1. **`FORCE ROW LEVEL SECURITY` is required, not optional.** Postgres exempts a table's *owner* from its own RLS policies by default, and the application's database role typically owns these tables (it ran the migrations that created them). Without `FORCE`, the application would silently bypass its own tenant isolation. `ENABLE` alone is not enough — this was confirmed by writing cross-tenant rows and querying them back before `FORCE` was added: both tenants' rows came back with `ENABLE` alone.
2. **The application's database role must never be a Postgres superuser** — superusers bypass RLS unconditionally, `FORCE` included, with no override.
3. **`current_setting('app.tenant_id', true)` (the `missing_ok=true` form) is required, not a simplification.** A session where `app.tenant_id` has never been set even once in that connection — a seed script, an admin tool, a fresh pooled connection — makes the single-argument `current_setting('app.tenant_id')` raise `unrecognized configuration parameter`, not a graceful empty result. This was found by running the actual seed script (`scripts/seed_platform_defaults.py`) against a real database, which errored until this fix was applied. With `missing_ok=true`, an unset variable evaluates to `NULL`, the equality never matches, and the policy still fails closed (zero rows for strictly tenant-owned tables; only the global `tenant_id IS NULL` rows for nullable-tenant tables) — it just does so without crashing the caller.
