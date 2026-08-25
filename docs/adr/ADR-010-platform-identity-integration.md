# ADR-010: Platform Identity integration (federated login handoff)

- Status: Accepted
- Date: 2026-08-25

## Context

The company introduced a separate Platform Identity service (sibling
repo `enterprise/platform`) as the single account/login layer for a
growing multi-product portfolio — see that repo's
`docs/adr/ADR-001-federated-identity-platform.md` and
`docs/adr/ADR-002-account-organization-and-cutover-scope.md`. Career
Compass AI is product #1 under that design. This ADR is the CCAI-side
half of that integration: what actually changes in this codebase, and
— just as importantly — what does not.

## Decision

1. **`platform_account_id` links a local `User` row to a canonical
   Platform Identity `Account`.** Added to `User`, not `Tenant` —
   entitlement checks and provisioning happen at login time, i.e.
   per-user, not per-tenant. Unique **per tenant**, not globally: the
   real account this integration launches with already has both a
   Personal CCAI tenant and a separate Enterprise (`scaledbrain`)
   tenant, and the same Platform Account legitimately links to a `User`
   row in each.
2. **`platform_org_id` links a `Tenant` to a Platform Identity
   `Organization`**, globally unique. Set only for Enterprise tenants
   whose access is granted at the org level on the platform side.
3. **The handoff is an exchange, not native token consumption.** A new
   public endpoint, `POST /identity/platform-handoff`, takes a
   platform-issued RS256 token, verifies its signature against
   `platform_identity_public_key_pem` (a public key — nothing secret to
   protect), resolves/JIT-provisions the local tenant+user, and mints a
   completely normal local CCAI JWT via the *existing*
   `InternalJWTProvider.claims_for_user`. Every other part of this
   app's RLS/session model (`get_tenant_scoped_session`,
   `verify_access_token`, the sliding-refresh dependency) is
   **unchanged** — a platform token is never accepted anywhere else,
   and CCAI's own `IdentityClaims`/IdentityProviderInterface contract
   gained no new shape to accommodate it.
4. **Tenant resolution branches on where the entitlement came from**,
   not on any explicit "account type" flag: if the caller's active
   `career_compass_ai` entitlement is org-scoped, resolve via
   `Tenant.platform_org_id` — an org with no linked tenant yet is a
   real `ORG_NOT_PROVISIONED` error, not something this service
   fabricates a tenant for. If the entitlement is direct (the Personal
   case), resolve via the existing `derive_personal_subdomain(email)`,
   JIT-creating a new Personal tenant through the *existing*
   `RegisterTenantService.execute_with_hashed_password` if none exists
   — reusing that service exactly as the real email-verification signup
   flow already does, not a second tenant-creation code path.
5. **No new multi-user provisioning for an already-existing,
   org-linked tenant.** If an org-linked tenant exists but has no user
   matching the platform account (by `platform_account_id`, or by
   email as a one-time link for a not-yet-migrated user), the handoff
   fails with `NO_MATCHING_USER` rather than creating a second user in
   that tenant. Career Compass AI has no invite/multi-user-per-tenant
   flow anywhere else in the app today (every Enterprise tenant has
   exactly one user); inventing one silently as a side effect of this
   integration would be a real, undiscussed feature addition, not
   plumbing.
6. **A platform-provisioned user gets an unusable local password**
   (`hash_password(secrets.token_urlsafe(32))`), not a blank or
   nullable `hashed_password` — the column stays required, and this
   user's only real login path is the platform handoff, from the
   moment their local row is first created.

## Consequences

- Career Compass AI's local `POST /identity/login` (email/password)
  keeps working, unaffected, for every existing account — this ADR
  does not disable it. Per the platform repo's own ADR-002, local login
  is disabled **only after** the handoff path is verified working
  end-to-end for the real migrated account — a separate, explicit
  cutover step, not a side effect of shipping this endpoint.
- A genuinely new dependency requirement: `pyjwt[crypto]` (RS256
  signature verification needs the `cryptography` backend) — made
  explicit in `pyproject.toml` rather than relying on it arriving as
  some other dependency's transitive install.
- Migrating the one real existing account (`bcmaharana@hotmail.com`,
  both its Personal and `scaledbrain` Enterprise tenants) is a separate
  follow-on step: backfill `platform_account_id` on its existing
  `User` rows and `platform_org_id` on the `scaledbrain` `Tenant` row,
  once the corresponding Platform Identity account and Organization
  exist. No existing CCAI data changes as part of that — it's a link,
  not a migration, per the platform repo's own ADR-001.

## Related

- `enterprise/platform/docs/adr/ADR-001-federated-identity-platform.md`
- `enterprise/platform/docs/adr/ADR-002-account-organization-and-cutover-scope.md`
- `docs/adr/ADR-003-authentication-strategy.md` — this repo's own
  existing JWT/session design, unchanged by this ADR.
