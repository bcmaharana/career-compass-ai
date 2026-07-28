"""List feature flags visible to the caller's tenant.

Returns both tenant-specific overrides and global defaults (the
repository already merges these — see
SqlAlchemyFeatureFlagRepository.list_for_tenant). Write/management
endpoints are deferred to Phase 9 (Analytics, Billing, Enterprise
Features) per the roadmap; Phase 1 establishes read access only, enough
for application services elsewhere to start gating behavior on flags.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.identity.entities import FeatureFlag
from app.domain.identity.repositories import FeatureFlagRepository


class ListFeatureFlagsService:
    def __init__(self, feature_flags: FeatureFlagRepository) -> None:
        self._feature_flags = feature_flags

    async def execute(self, *, tenant_id: UUID) -> list[FeatureFlag]:
        return await self._feature_flags.list_for_tenant(tenant_id)
