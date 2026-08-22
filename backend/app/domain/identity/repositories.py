"""Repository interfaces for the Identity bounded context.

Application services depend only on these Protocols. Concrete
implementations live in app/adapters/db/repositories.py (SQLAlchemy) and
never leak into application/ or domain/. Unit tests substitute in-memory
fakes against these same interfaces (see tests/unit/) rather than mocking
SQLAlchemy internals.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.identity.entities import (
    AuditEvent,
    FeatureFlag,
    Organization,
    PasswordResetToken,
    PendingSignup,
    Role,
    Tenant,
    User,
    UserRoleAssignment,
)


class TenantRepository(Protocol):
    async def create(self, tenant: Tenant) -> Tenant: ...
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...
    async def get_by_subdomain(self, subdomain: str) -> Tenant | None: ...


class OrganizationRepository(Protocol):
    async def create(self, organization: Organization) -> Organization: ...
    async def get_by_id(self, tenant_id: UUID, org_id: UUID) -> Organization | None: ...


class UserRepository(Protocol):
    async def create(self, user: User) -> User: ...
    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None: ...
    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None: ...
    async def get_by_phone_e164(self, tenant_id: UUID, phone_e164: str) -> User | None: ...
    async def update(self, user: User) -> User: ...
    async def set_handle(self, *, tenant_id: UUID, user_id: UUID, handle: str) -> bool:
        """Attempts to set `handle` on this user; returns False (does not
        raise) if it's already taken by ANY user in ANY tenant, True on
        success. This is deliberately a try-then-check-the-constraint
        operation, not a proactive "does this handle already exist"
        SELECT: `handle` is globally unique (see the owning migration's
        functional index on lower(handle)), but `users` is RLS-protected
        per-tenant — a SELECT under a normal tenant-scoped session can
        never see another tenant's row, so a proactive cross-tenant
        existence check would silently give false negatives. The unique
        INDEX itself, unlike a SELECT policy, is still enforced against
        every row in the table regardless of which tenant is currently
        bound — so attempting the write and catching the resulting
        constraint violation is the only correct way to detect a
        cross-tenant collision here."""
        ...


class RoleRepository(Protocol):
    async def get_by_name(self, name: str, *, tenant_id: UUID | None = None) -> Role | None: ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[Role]: ...
    async def assign_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment: ...


class AuditEventRepository(Protocol):
    async def record(self, event: AuditEvent) -> AuditEvent: ...
    async def list_recent(self, tenant_id: UUID, *, limit: int = 50) -> list[AuditEvent]: ...


class FeatureFlagRepository(Protocol):
    async def list_for_tenant(self, tenant_id: UUID) -> list[FeatureFlag]: ...


class PasswordResetTokenRepository(Protocol):
    async def create(self, token: PasswordResetToken) -> PasswordResetToken: ...

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Deliberately no tenant_id parameter — this is the RLS-exempt,
        pre-tenant-context lookup a confirm-reset request starts from,
        the same shape as TenantRepository.get_by_subdomain."""
        ...

    async def invalidate_unused_for_user(self, tenant_id: UUID, user_id: UUID) -> None: ...
    async def mark_used(self, token_id: UUID) -> None: ...


class PendingSignupRepository(Protocol):
    async def create(self, signup: PendingSignup) -> PendingSignup: ...

    async def get_by_token_hash(self, token_hash: str) -> PendingSignup | None:
        """Deliberately no tenant_id parameter — no tenant exists yet
        for a pending signup at all, the same RLS-exempt shape as
        PasswordResetTokenRepository.get_by_token_hash."""
        ...

    async def delete(self, signup_id: UUID) -> None: ...
    async def delete_all_for_email(self, email: str) -> None: ...


class PersonalPhoneLoginRepository(Protocol):
    """RLS-exempt cross-tenant lookup for Personal-account phone login —
    see `personal_phone_logins` (no ENABLE/FORCE ROW LEVEL SECURITY,
    same reasoning as PasswordResetTokenRepository: must be resolvable
    before any tenant context is bound). Only Personal-tenant users are
    ever registered here (see `is_personal_subdomain` in
    app/domain/identity/personal_accounts.py) — Enterprise phone numbers
    stay purely tenant-scoped via `UserRepository.get_by_phone_e164`,
    unaffected by this table.
    """

    async def upsert(self, *, phone_e164: str, tenant_id: UUID, user_id: UUID) -> None:
        """Registers phone_e164 as this user's login number, replacing
        any prior number registered for the same user_id. Raises
        ConflictError if phone_e164 is already registered to a
        *different* user_id — the phone number is the table's primary
        key, so at most one Personal account may claim it at a time."""
        ...

    async def get_tenant_id(self, phone_e164: str) -> UUID | None: ...
    async def delete_for_user(self, user_id: UUID) -> None:
        """Invalidates any previous unconfirmed signup attempts for this
        email — mirrors PasswordResetTokenRepository's
        invalidate_unused_for_user, just via delete since there's no
        used_at state worth keeping here (unlike a used reset token,
        an abandoned pending signup has no audit value once superseded).
        """
        ...


class TenantContextBinder(Protocol):
    """Binds a tenant_id to the current unit-of-work's RLS context.

    Exists so application services can trigger RLS scoping (required
    before creating tenant-owned rows for a tenant that doesn't exist
    yet at request-middleware time, e.g. during tenant registration)
    without importing SQLAlchemy or knowing anything about `SET LOCAL`.
    The concrete implementation lives in app/adapters/db and simply calls
    set_tenant_context on the current session.
    """

    async def bind(self, tenant_id: UUID) -> None: ...
