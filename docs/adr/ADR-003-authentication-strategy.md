# ADR-003: Internal JWT Auth Behind an Identity Provider Interface

## Status
Accepted

## Context
Enterprise customers will eventually require SSO/OIDC integration (Auth0, Okta, Azure Entra ID). Building full external-IdP integration before the platform has any real users would delay Phase 1 for capability that isn't yet needed, but designing internal auth in a way that later requires a rewrite to support SSO would be worse.

## Decision
Define `IdentityProviderInterface` (an abstract contract) in `app/core/identity_provider_interface.py` from Phase 0. Phase 1 implements exactly one concrete provider against it — `InternalJWTProvider` (email/password, Argon2id hashing, JWT access + Redis-backed refresh tokens). External providers (`Auth0Provider`, `OktaProvider`, `AzureEntraProvider`) implement the same interface later, selected per-tenant via tenant configuration, without changing any calling code in `application/` or `api/`.

## Consequences
**Positive:**
- Phase 1 ships fast with a single, well-understood auth mechanism.
- Adding SSO later is additive (a new adapter), not a refactor of existing call sites.
- Application services never know which identity provider authenticated a user — they only see normalized identity claims.

**Negative / accepted trade-offs:**
- The interface must be designed carefully enough now that it doesn't need a breaking change when the first external provider is added — this is a real risk, mitigated by shaping the interface around the common denominator (identity claims: user identifier, email, tenant, roles) rather than JWT-specific details.

## Revisit Trigger
Implement the first external provider adapter when a specific enterprise customer or deal requires SSO — do not build speculative adapters before then.
