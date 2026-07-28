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
    async def update(self, user: User) -> User: ...


class RoleRepository(Protocol):
    async def get_by_name(self, name: str, *, tenant_id: UUID | None = None) -> Role | None: ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[Role]: ...
    async def assign_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment: ...


class AuditEventRepository(Protocol):
    async def record(self, event: AuditEvent) -> AuditEvent: ...
    async def list_recent(self, tenant_id: UUID, *, limit: int = 50) -> list[AuditEvent]: ...


class FeatureFlagRepository(Protocol):
    async def list_for_tenant(self, tenant_id: UUID) -> list[FeatureFlag]: ...


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
