"""Request/response schemas for the identity API.

Kept separate from both the domain entities (dataclasses, framework-free)
and the application-layer DTOs — these are the one layer allowed to know
about Pydantic and HTTP-facing field naming.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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


def _require_agreed_to_terms(value: bool) -> bool:
    if not value:
        raise ValueError(
            "You must agree to the Terms of Service and Privacy Policy to create an account."
        )
    return value


class PersonalSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)
    agreed_to_terms: bool

    _validate_agreed_to_terms = field_validator("agreed_to_terms")(_require_agreed_to_terms)


class OrganizationSignupRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=255)
    subdomain: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9-]+$")
    organization_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_first_name: str = Field(min_length=1, max_length=150)
    admin_last_name: str = Field(min_length=1, max_length=150)
    admin_password: str = Field(min_length=8, max_length=128)
    agreed_to_terms: bool

    _validate_agreed_to_terms = field_validator("agreed_to_terms")(_require_agreed_to_terms)


class SignupRequestResponse(BaseModel):
    #: Not deliberately-generic the way password-reset's response is
    #: (there's no enumeration concern to protect here — duplicate
    #: email/subdomain is already reported specifically, immediately,
    #: as a 409 before this response would ever be returned) — this is
    #: just the plain "we sent it" acknowledgment.
    message: str = "Check your email for a verification link to finish creating your account."


class VerifySignupRequest(BaseModel):
    token: str = Field(min_length=1)


class LoginRequest(BaseModel):
    #: None/omitted means "Personal account" — the frontend never asks
    #: a Personal user for a subdomain, at signup or at login (see
    #: AuthenticateUserService.execute / derive_personal_subdomain).
    subdomain: str | None = Field(default=None, max_length=63)
    email: EmailStr
    password: str = Field(min_length=1)


class PhoneLoginRequest(BaseModel):
    #: None/omitted means "Personal account" — same convention as
    #: LoginRequest.subdomain (see AuthenticateUserService.execute_phone).
    subdomain: str | None = Field(default=None, max_length=63)
    #: The ID token returned by the Firebase JS SDK's
    #: confirmationResult.confirm(code) after the user enters the SMS
    #: code — never the raw code itself, which never reaches this
    #: backend at all (see app/adapters/identity_providers/firebase_phone.py).
    firebase_id_token: str = Field(min_length=1)


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


class RequestPasswordResetRequest(BaseModel):
    #: Same "None means Personal account" convention as LoginRequest.
    subdomain: str | None = Field(default=None, max_length=63)
    email: EmailStr


class RequestPasswordResetResponse(BaseModel):
    message: str = "If an account exists for that email, a reset link has been sent."


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str = "Your password has been reset. You can now sign in."


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
    visa_status: str | None = Field(default=None, max_length=100)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    other_professional_url: str | None = Field(default=None, max_length=2048)
    middle_name: str | None = Field(default=None, max_length=150)
    #: Format-validated in UpdateUserProfileService (2-32 chars,
    #: alphanumeric/hyphen/underscore) — kept permissive (bare
    #: max_length) here since the friendlier custom error message lives
    #: in the service layer, matching how country's 2-letter format is
    #: also validated there rather than via a Pydantic pattern.
    handle: str | None = Field(default=None, max_length=32)


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
    visa_status: str | None
    linkedin_url: str | None
    other_professional_url: str | None
    middle_name: str | None
    handle: str | None
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
