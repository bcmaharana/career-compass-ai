"""Register a new tenant.

Creates the Tenant, its first Organization, and an initial admin User,
assigning the global "organization_admin" role. This is the one flow in
the system that creates tenant-owned rows for a tenant that didn't exist
a moment ago — see TenantContextBinder in
app/domain/identity/repositories.py for why it needs to bind RLS context
explicitly rather than relying on request middleware (which only knows a
tenant_id for *already authenticated* requests against an *existing*
tenant).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.identity.audit_service import AuditService
from app.application.identity.dto import NewTenantResult
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.domain.identity.entities import Organization, Tenant, User, UserRoleAssignment
from app.domain.identity.repositories import (
    OrganizationRepository,
    RoleRepository,
    TenantContextBinder,
    TenantRepository,
    UserRepository,
)

DEFAULT_ADMIN_ROLE_NAME = "organization_admin"


class RegisterTenantService:
    def __init__(
        self,
        tenants: TenantRepository,
        organizations: OrganizationRepository,
        users: UserRepository,
        roles: RoleRepository,
        tenant_context: TenantContextBinder,
        audit: AuditService,
    ) -> None:
        self._tenants = tenants
        self._organizations = organizations
        self._users = users
        self._roles = roles
        self._tenant_context = tenant_context
        self._audit = audit

    async def execute(
        self,
        *,
        tenant_name: str,
        subdomain: str,
        organization_name: str,
        admin_email: str,
        admin_salutation: str | None,
        admin_first_name: str,
        admin_last_name: str,
        admin_password: str,
    ) -> NewTenantResult:
        if await self._tenants.get_by_subdomain(subdomain) is not None:
            raise ConflictError(
                f"Subdomain '{subdomain}' is already in use.", code="SUBDOMAIN_TAKEN"
            )

        now = datetime.now(UTC)
        tenant = Tenant(
            id=uuid.uuid4(),
            name=tenant_name,
            subdomain=subdomain,
            plan_tier="starter",
            status="active",
            created_at=now,
            updated_at=now,
        )
        tenant = await self._tenants.create(tenant)

        # Everything below is tenant-owned and RLS-protected — bind
        # context to the tenant we just created before touching any of it.
        await self._tenant_context.bind(tenant.id)

        organization = Organization(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=organization_name,
            parent_org_id=None,
            created_at=now,
            updated_at=now,
        )
        organization = await self._organizations.create(organization)

        admin_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            org_id=organization.id,
            email=admin_email,
            salutation=admin_salutation,
            first_name=admin_first_name,
            last_name=admin_last_name,
            hashed_password=hash_password(admin_password),
            status="active",
            mfa_enabled=False,
            created_at=now,
            updated_at=now,
        )
        admin_user = await self._users.create(admin_user)

        admin_role = await self._roles.get_by_name(DEFAULT_ADMIN_ROLE_NAME, tenant_id=None)
        if admin_role is None:
            raise NotFoundError(
                "Default 'organization_admin' role is not seeded. "
                "Run scripts/seed_platform_defaults.py.",
                code="ROLE_NOT_SEEDED",
            )

        await self._roles.assign_to_user(
            UserRoleAssignment(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=admin_user.id,
                role_id=admin_role.id,
                org_id=organization.id,
            )
        )

        await self._audit.record(
            tenant_id=tenant.id,
            user_id=admin_user.id,
            action="tenant.created",
            resource_type="tenant",
            resource_id=tenant.id,
            metadata={"subdomain": subdomain},
        )
        await self._audit.record(
            tenant_id=tenant.id,
            user_id=admin_user.id,
            action="user.created",
            resource_type="user",
            resource_id=admin_user.id,
            metadata={"role": DEFAULT_ADMIN_ROLE_NAME, "initial_admin": True},
        )

        return NewTenantResult(
            tenant_id=tenant.id,
            organization_id=organization.id,
            admin_user_id=admin_user.id,
            admin_email=admin_user.email,
        )
