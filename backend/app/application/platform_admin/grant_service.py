"""Grant/manage platform-admin access for other users.

Resolving a target user to grant access to reuses the exact same
subdomain-resolution pattern login already uses
(AuthenticateUserService.execute): if no subdomain is given, the target
is a Personal account and its tenant is resolved via
derive_personal_subdomain(email); otherwise the caller-supplied
Enterprise subdomain is used as-is. Tenant context is bound just long
enough to look the target user up — the actual write, to
platform_admins, goes to a table with no RLS at all (see its own module
docstring in app/domain/platform_admin/entities.py).
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import TenantContextBinder, TenantRepository, UserRepository
from app.domain.platform_admin.entities import PlatformAdminGrant
from app.domain.platform_admin.permissions import (
    ALL_PLATFORM_PERMISSION_CODES,
    PLATFORM_ADMINS_MANAGE,
)
from app.domain.platform_admin.repositories import PlatformAdminRepository


class PlatformAdminService:
    def __init__(
        self,
        grants: PlatformAdminRepository,
        tenants: TenantRepository,
        users: UserRepository,
        tenant_context: TenantContextBinder,
    ) -> None:
        self._grants = grants
        self._tenants = tenants
        self._users = users
        self._tenant_context = tenant_context

    async def get_my_grant(self, *, tenant_id: UUID, user_id: UUID) -> PlatformAdminGrant | None:
        return await self._grants.get_for_user(tenant_id, user_id)

    async def list_admins(self) -> list[PlatformAdminGrant]:
        return await self._grants.list_all()

    async def grant(
        self,
        *,
        email: str,
        subdomain: str | None,
        permission_codes: frozenset[str],
        granted_by_user_id: UUID,
    ) -> PlatformAdminGrant:
        self._validate_codes(permission_codes)

        resolved_subdomain = subdomain or derive_personal_subdomain(email)
        tenant = await self._tenants.get_by_subdomain(resolved_subdomain)
        if tenant is None:
            raise NotFoundError(
                "No account found for that email/organization.", code="ACCOUNT_NOT_FOUND"
            )

        await self._tenant_context.bind(tenant.id)
        user = await self._users.get_by_email(tenant.id, email)
        if user is None:
            raise NotFoundError(
                "No account found for that email/organization.", code="ACCOUNT_NOT_FOUND"
            )

        return await self._grants.upsert(
            tenant_id=tenant.id,
            user_id=user.id,
            email=user.email,
            full_name=user.display_name or user.email,
            subdomain=tenant.subdomain,
            permission_codes=permission_codes,
            granted_by_user_id=granted_by_user_id,
        )

    async def update_permissions(
        self, *, grant_id: UUID, permission_codes: frozenset[str], granted_by_user_id: UUID
    ) -> PlatformAdminGrant:
        self._validate_codes(permission_codes)

        existing = await self._grants.get_by_id(grant_id)
        if existing is None:
            raise NotFoundError(
                "Platform admin grant not found.", code="PLATFORM_ADMIN_GRANT_NOT_FOUND"
            )

        if (
            PLATFORM_ADMINS_MANAGE in existing.permission_codes
            and PLATFORM_ADMINS_MANAGE not in permission_codes
        ):
            await self._raise_if_last_admins_manage_holder()

        return await self._grants.upsert(
            tenant_id=existing.tenant_id,
            user_id=existing.user_id,
            email=existing.email,
            full_name=existing.full_name,
            subdomain=existing.subdomain,
            permission_codes=permission_codes,
            granted_by_user_id=granted_by_user_id,
        )

    async def revoke(self, *, grant_id: UUID) -> None:
        existing = await self._grants.get_by_id(grant_id)
        if existing is None:
            return
        if PLATFORM_ADMINS_MANAGE in existing.permission_codes:
            await self._raise_if_last_admins_manage_holder()
        await self._grants.delete(grant_id)

    def _validate_codes(self, permission_codes: frozenset[str]) -> None:
        unknown = permission_codes - ALL_PLATFORM_PERMISSION_CODES
        if unknown:
            raise ValidationError(f"Unknown permission code(s): {', '.join(sorted(unknown))}")

    async def _raise_if_last_admins_manage_holder(self) -> None:
        count = await self._grants.count_with_permission(PLATFORM_ADMINS_MANAGE)
        if count <= 1:
            raise ValidationError(
                "Cannot remove the last remaining platform admin with permission to manage "
                "other admins — grant that permission to someone else first.",
                code="LAST_PLATFORM_ADMIN",
            )
