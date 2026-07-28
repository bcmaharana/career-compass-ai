# Security Architecture — Career Compass AI

## Configuration & Secrets

- All configuration loaded via `pydantic-settings` from environment variables; no secrets committed to source control.
- Local dev uses `.env` (gitignored); `.env.example` documents required keys with placeholder values.
- Production is expected to inject secrets via a secrets manager (AWS Secrets Manager / HashiCorp Vault) — the config loader doesn't care where the environment variables come from, so swapping the secrets backend requires no application code change.

## Authentication

- Passwords hashed with **Argon2id** (`passlib[argon2]`), not bcrypt-only — current OWASP-recommended default.
- Access tokens: JWT, short-lived (~15 min).
- Refresh tokens: opaque, stored server-side (Redis in later phases) so they can be revoked; not just a longer-lived JWT.
- `IdentityProviderInterface` (see `app/core/identity_provider_interface.py`) abstracts internal-JWT auth from future external OIDC providers (Auth0, Okta, Azure Entra ID) — implemented in Phase 1, designed now so the interface shape is settled early.

## Authorization

- RBAC, permissions stored in the database (not hard-coded), enforced at the **application service layer**, not just at the router — so an internal caller bypassing the HTTP layer still can't skip a permission check.

## API Security

- Input validation via Pydantic models at every API boundary — malformed input is rejected before reaching application services.
- Consistent JSON error shape (see below) so no endpoint leaks stack traces or internal details in a response body.
- CORS allow-list scoped per tenant subdomain (implemented once tenant resolution exists in Phase 1).
- Rate limiting at the gateway/middleware layer (foundation laid in Phase 0 middleware scaffolding; enforcement rules land with Phase 1 identity).

## Error Response Shape

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested resource was not found.",
    "request_id": "b3f1c2..."
  }
}
```

Domain/application code raises typed exceptions (`NotFoundError`, `ValidationError`, etc.); a single FastAPI exception handler translates them to this shape and the correct HTTP status. No raw exception messages or tracebacks are ever returned to a client.

## Audit Logging

- `AuditEvent` records are append-only; Phase 1 adds a database trigger rejecting `UPDATE`/`DELETE` on the table.
- Phase 0 establishes the logging *interface* in `app/core/logging.py` and the middleware seam in `app/api/middleware/audit.py`-equivalent (wired fully once auth/tenant context exists).

## Dependency Vulnerability Scanning

- `pip-audit` (or `safety`) run in CI on every push against `backend/pyproject.toml`'s locked dependencies.
- `npm audit` equivalent for the frontend once it exists (Phase 0.2).
- Both wired into the GitHub Actions CI skeleton created in Phase 0 (`.github/workflows/backend-ci.yml`).

## Compliance Readiness

Audit immutability, data retention fields, and tenant isolation via RLS are in place from Phase 1 onward specifically so SOC 2 / ISO 27001 evidence-gathering later doesn't require a schema rewrite. GDPR data-export and right-to-erasure are modeled as application-service operations (not UI features) from the point `User`/`CareerProfile` exist, even before they're exposed anywhere.
