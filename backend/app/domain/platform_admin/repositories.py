"""Repository interfaces for the platform-admin bounded context.

See app/domain/identity/repositories.py's module docstring for the same
"application services depend only on these Protocols" convention this
follows.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.platform_admin.entities import PlatformAdminGrant, PlatformSetting


class PlatformAdminRepository(Protocol):
    async def get_for_user(self, tenant_id: UUID, user_id: UUID) -> PlatformAdminGrant | None: ...

    async def get_by_id(self, grant_id: UUID) -> PlatformAdminGrant | None: ...

    async def list_all(self) -> list[PlatformAdminGrant]: ...

    async def count_with_permission(self, permission_code: str) -> int:
        """Used to block revoking/downgrading the last remaining holder
        of platform.admins.manage — the system must never end up with
        no one able to grant access back."""
        ...

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        email: str,
        full_name: str,
        subdomain: str,
        permission_codes: frozenset[str],
        granted_by_user_id: UUID,
    ) -> PlatformAdminGrant:
        """Creates a new grant, or replaces the permission_codes/email/
        full_name/subdomain of an existing one for the same (tenant_id,
        user_id) pair — upsert, not two separate methods, since the
        caller (the admin API) never needs to distinguish the two
        cases."""
        ...

    async def delete(self, grant_id: UUID) -> None: ...


class PlatformSettingsRepository(Protocol):
    async def get(self, key: str) -> PlatformSetting | None: ...

    async def list_all(self) -> list[PlatformSetting]: ...

    async def upsert(
        self, *, key: str, value: str, description: str, updated_by_user_id: UUID | None
    ) -> PlatformSetting: ...

    async def seed_if_missing(self, *, key: str, value: str, description: str) -> None:
        """Insert only if the key doesn't already exist yet — used by
        the seed script so a real admin edit is never clobbered by a
        reseed, matching _seed_permissions/_seed_roles's own
        idempotency convention in scripts/seed_platform_defaults.py."""
        ...
