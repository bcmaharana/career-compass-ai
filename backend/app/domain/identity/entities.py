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
