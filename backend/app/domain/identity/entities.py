"""Identity domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. These are what
domain and application services operate on; the ORM models in
app/adapters/db/models.py are a separate, parallel representation that
repositories translate to and from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Tenant:
    id: UUID
    name: str
    subdomain: str
    plan_tier: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Organization:
    id: UUID
    tenant_id: UUID
    name: str
    parent_org_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class User:
    id: UUID
    tenant_id: UUID
    org_id: UUID | None
    email: str
    salutation: str | None
    first_name: str
    last_name: str
    hashed_password: str
    status: str
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    last_login_at: datetime | None = None
    phone_number: str | None = None
    #: E.164 form of phone_number (e.g. "+14155552671"), derived
    #: automatically whenever phone_number+country are saved together
    #: (see UpdateUserProfileService) — the only field phone login
    #: (InternalJWTProvider.authenticate_with_phone) actually looks up
    #: against, since it's what Firebase's verified token reports too.
    #: None whenever phone_number can't be parsed for the given country,
    #: which just means phone login isn't available yet, not an error.
    phone_number_e164: str | None = None
    #: ISO 3166-1 alpha-2 (e.g. "US") — drives phone-number formatting on
    #: the frontend (libphonenumber-js needs a country to know which
    #: national format/length rules apply).
    country: str | None = None
    #: BCP 47 language tag (e.g. "en", "en-US", "fr") — a stored
    #: preference only; no i18n system consumes it yet.
    language: str | None = None
    #: Structured address components rather than one free-text field —
    #: the frontend renders/labels them in a country-appropriate layout
    #: (US: street/city/state/ZIP; international: street/city/postal
    #: code/region) driven off `country`, the same way phone-number
    #: formatting is driven off `country` client-side.
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    #: Explicit override of which AI Platform model powers this user's
    #: chats (app/ai_platform/models/registry.py). None means "use the
    #: platform default" — see ModelRegistry.get_active_model.
    preferred_model_version_id: UUID | None = None
    #: When/which version of the Terms of Service + Privacy Policy this
    #: user agreed to at signup (see app/domain/identity/legal_terms.py).
    #: Both None for any account created before this was tracked —
    #: deliberately not backfilled, since fabricating retroactive
    #: consent would be dishonest. Real consent is captured once, at
    #: signup request time, and carried through to here by
    #: VerifySignupService — see RegisterTenantService.execute_with_hashed_password.
    agreed_to_terms_at: datetime | None = None
    terms_version: str | None = None
    #: A fixed set of standard US work-authorization values (see
    #: frontend/src/lib/visa-status-options.ts) — stored as plain text
    #: like language/country rather than a DB-level enum, matching this
    #: codebase's existing "frontend dropdown constrains the value,
    #: backend just stores the string" convention for country/language.
    visa_status: str | None = None
    linkedin_url: str | None = None
    other_professional_url: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active" and self.deleted_at is None

    @property
    def display_name(self) -> str:
        parts = [part for part in (self.salutation, self.first_name, self.last_name) if part]
        return " ".join(parts)


@dataclass(slots=True)
class Permission:
    id: UUID
    code: str
    description: str


@dataclass(slots=True)
class Role:
    id: UUID
    tenant_id: UUID | None  # None = global/system role definition
    name: str
    permission_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True)
class UserRoleAssignment:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    role_id: UUID
    org_id: UUID | None


@dataclass(slots=True)
class AuditEvent:
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    occurred_at: datetime
    metadata: dict[str, object]
    ip_address: str | None


@dataclass(slots=True)
class FeatureFlag:
    id: UUID
    tenant_id: UUID | None  # None = global default
    key: str
    enabled: bool
    config: dict[str, object]


@dataclass(slots=True)
class PasswordResetToken:
    """A one-time, short-lived token for the "forgot password" flow.

    Deliberately RLS-exempt (see adapters/db/models/identity.py) — the
    confirm-reset step must resolve which tenant a token belongs to
    before any tenant context can be bound, the same chicken-and-egg
    problem Tenant itself has for pre-login subdomain lookup.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime


@dataclass(slots=True)
class PendingSignup:
    """An unconfirmed signup — holds everything needed to create a real
    Tenant/Organization/User, but nothing is written to those tables
    until the emailed verification link is clicked.

    Deliberately RLS-exempt, same reasoning as PasswordResetToken: no
    tenant exists yet at all for a pending signup, so there is nothing
    to bind tenant context to before this must be resolvable.

    tenant_name/subdomain/organization_name are None for a "personal"
    signup — those are computed at confirm time (subdomain via
    derive_personal_subdomain, tenant_name from the person's own name,
    organization_name defaults to "Personal"), not stored, since
    they're always the same deterministic values for a given email.
    """

    id: UUID
    kind: str  # "personal" | "enterprise"
    email: str
    hashed_password: str
    first_name: str
    last_name: str
    tenant_name: str | None
    subdomain: str | None
    organization_name: str | None
    token_hash: str
    expires_at: datetime
    created_at: datetime
    #: Required — a signup request can't be created without agreeing
    #: (see PersonalSignupRequest/OrganizationSignupRequest's
    #: agreed_to_terms field). Carried through to the real User row by
    #: VerifySignupService once the link is clicked.
    agreed_to_terms_at: datetime
    terms_version: str
