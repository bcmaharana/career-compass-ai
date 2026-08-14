"""Application-layer DTOs for the Identity module.

Distinct from both the domain entities (app/domain/identity/entities.py)
and the API's Pydantic request/response schemas
(app/api/v1/identity/schemas.py). These carry data across the
application-service boundary without exposing internal domain object
shapes directly to the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class NewTenantResult:
    tenant_id: UUID
    organization_id: UUID
    admin_user_id: UUID
    admin_email: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    token_type: str
    user_id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    first_name: str
    last_name: str
    salutation: str | None
    last_login_at: str | None
    roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurrentUserResult:
    user_id: UUID
    tenant_id: UUID
    org_id: UUID | None
    email: str
    full_name: str
    salutation: str | None
    first_name: str
    last_name: str
    phone_number: str | None
    country: str | None
    language: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    visa_status: str | None
    linkedin_url: str | None
    other_professional_url: str | None
    roles: tuple[str, ...]
