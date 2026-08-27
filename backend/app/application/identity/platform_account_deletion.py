"""Deletes this CCAI tenant's data in response to a Hub-side account
deletion — the counterpart to PlatformHandoffService, called via a new
public endpoint the Hub's own DeleteAccountService POSTs to.

Resolution mirrors PlatformHandoffService's own two rules exactly,
just for delete instead of provision: `org_id` set (an Enterprise
account) resolves via `Tenant.platform_org_id` — a precise, deliberate
1:1 link (an Enterprise Account is 1:1 with its Organization, see
Membership's own docstring on the Hub), no derivation or guessing
involved, so no extra ownership check is needed once that lookup
succeeds. `org_id` None (a Personal account) resolves via the
deterministic `derive_personal_subdomain(email)`, the same
pre-context-safe lookup login already uses — since that's a
computed guess rather than a direct link, it's followed by a check
that the resolved tenant's own user actually has this exact
`platform_account_id`, so an unrelated local account that merely
shares the email's subdomain hash is never touched.

Idempotent: no matching (or already-deleted) tenant either way is a
clean no-op, not an error — the Hub's own deletion already succeeded
regardless of what this endpoint finds.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.identity.account_deletion import AccountDeletionRepository
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import TenantContextBinder, TenantRepository, UserRepository


class PlatformAccountDeletionService:
    def __init__(
        self,
        tenants: TenantRepository,
        users: UserRepository,
        account_deletion: AccountDeletionRepository,
        tenant_context: TenantContextBinder,
    ) -> None:
        self._tenants = tenants
        self._users = users
        self._account_deletion = account_deletion
        self._tenant_context = tenant_context

    async def execute(
        self, *, platform_account_id: str, email: str, org_id: str | None
    ) -> None:
        if org_id is not None:
            tenant = await self._tenants.get_by_platform_org_id(UUID(org_id))
            if tenant is None:
                return
            await self._tenant_context.bind(tenant.id)
            await self._account_deletion.delete_tenant(tenant.id)
            return

        subdomain = derive_personal_subdomain(email)
        tenant = await self._tenants.get_by_subdomain(subdomain)
        if tenant is None:
            return

        await self._tenant_context.bind(tenant.id)
        user = await self._users.get_by_email(tenant.id, email)
        if user is None:
            return
        if (
            user.platform_account_id is not None
            and str(user.platform_account_id) != platform_account_id
        ):
            # Deterministic-subdomain collision with an unrelated,
            # never-linked local account — never happened in practice
            # (sha256-derived), but a real safety check costs nothing.
            return

        await self._account_deletion.delete_tenant(tenant.id)
