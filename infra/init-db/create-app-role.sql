-- Creates the restricted, non-superuser role the application actually
-- connects as at runtime (DATABASE_URL). `compass` (the role that runs
-- migrations, via MIGRATIONS_DATABASE_URL) stays a superuser and keeps
-- owning every table — but Postgres superusers always bypass Row-Level
-- Security regardless of FORCE ROW LEVEL SECURITY, so the app itself
-- must never connect as `compass`. See docs/architecture/
-- multi-tenancy-design.md and the identity-foundation migration's own
-- "the application's DB role must never be a superuser" comment, which
-- anticipated exactly this fix.
--
-- Idempotent — safe to re-run. Invoked two ways:
--   1. Manually, once, against each already-initialized database this
--      fix is being retrofitted onto (dev career_compass/
--      career_compass_test, prod career_compass) — Postgres only
--      auto-runs docker-entrypoint-initdb.d/ scripts on a genuinely
--      fresh (empty) data directory, so it can't reach those.
--   2. Automatically, via docker-entrypoint-initdb.d/, for any future
--      fresh cluster (see the .sh wrapper alongside this file).
--
-- Expects two psql variables: -v app_password='...' -v dbname='...'

-- psql's :'var' substitution doesn't reach inside a dollar-quoted
-- DO $$ ... $$ block, so idempotent role creation uses \gexec instead:
-- this SELECT only produces a row (hence only executes CREATE ROLE)
-- when the role doesn't already exist.
SELECT 'CREATE ROLE compass_app WITH LOGIN PASSWORD ''' || :'app_password' ||
       ''' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'compass_app')
\gexec

GRANT CONNECT ON DATABASE :"dbname" TO compass_app;
GRANT USAGE ON SCHEMA public TO compass_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO compass_app;

-- Makes this durable: every future migration's new tables (created by
-- `compass`, via `alembic upgrade head`) are automatically granted to
-- compass_app without needing a manual grant step per migration.
ALTER DEFAULT PRIVILEGES FOR ROLE compass IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO compass_app;
