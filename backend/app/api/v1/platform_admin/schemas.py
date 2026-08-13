"""Request/response schemas for the platform-admin API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MyPlatformAdminResponse(BaseModel):
    #: Empty for any caller who isn't a platform admin at all — the
    #: frontend uses "non-empty" as its own "am I an admin" check rather
    #: than a separate boolean, so there's exactly one source of truth.
    permission_codes: list[str]


class PlatformPermissionResponse(BaseModel):
    code: str
    description: str


class PlatformSettingResponse(BaseModel):
    id: UUID
    key: str
    value: str
    description: str
    updated_at: datetime
    updated_by_user_id: UUID | None


class UpdatePlatformSettingRequest(BaseModel):
    value: str = Field(min_length=1)
    description: str = ""


class PlatformAdminGrantResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    email: str
    full_name: str
    permission_codes: list[str]
    granted_at: datetime
    granted_by_user_id: UUID


class GrantPlatformAdminRequest(BaseModel):
    email: str = Field(min_length=1)
    #: None = Personal account (tenant resolved via derive_personal_subdomain).
    #: Set for an Enterprise account, same as the login form's Organization field.
    subdomain: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class UpdatePlatformAdminRequest(BaseModel):
    permission_codes: list[str]
