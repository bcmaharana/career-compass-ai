"""Request/response schemas for the identity API.

Kept separate from both the domain entities (dataclasses, framework-free)
and the application-layer DTOs — these are the one layer allowed to know
about Pydantic and HTTP-facing field naming.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterTenantRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=255)
    subdomain: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9-]+$")
    organization_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_salutation: str | None = Field(default=None, max_length=20)
    admin_first_name: str = Field(min_length=1, max_length=150)
    admin_last_name: str = Field(min_length=1, max_length=150)
    admin_password: str = Field(min_length=8, max_length=128)


class RegisterTenantResponse(BaseModel):
    tenant_id: UUID
    organization_id: UUID
    admin_user_id: UUID
    admin_email: str


class LoginRequest(BaseModel):
    subdomain: str = Field(min_length=1, max_length=63)
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
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
    roles: list[str]


class UpdateCurrentUserRequest(BaseModel):
    salutation: str | None = Field(default=None, max_length=20)
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=2)
    language: str | None = Field(default=None, max_length=10)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)


class CurrentUserResponse(BaseModel):
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
    roles: list[str]


class AuditEventResponse(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    occurred_at: str
    metadata: dict[str, object]


class FeatureFlagResponse(BaseModel):
    id: UUID
    key: str
    enabled: bool
    config: dict[str, object]
    is_global_default: bool
