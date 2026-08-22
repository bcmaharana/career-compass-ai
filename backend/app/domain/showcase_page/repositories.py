"""Repository interfaces for the Showcase Page / public-sharing bounded
context. Application services depend only on these Protocols — see
app/domain/interview_prep/repositories.py for the established pattern
this follows.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.showcase_page.entities import PublicShareLink, ShareableResourceType, ShowcasePage


class ShowcasePageRepository(Protocol):
    async def create(self, page: ShowcasePage) -> ShowcasePage: ...
    async def get_by_target_role(
        self, tenant_id: UUID, target_role_id: UUID
    ) -> ShowcasePage | None: ...
    async def get_by_id(self, tenant_id: UUID, page_id: UUID) -> ShowcasePage | None: ...
    async def update(self, page: ShowcasePage) -> ShowcasePage: ...


class PublicShareLinkRepository(Protocol):
    """Backed by the RLS-exempt `public_share_links` table — every method
    here is deliberately NOT tenant-scoped in its query (no tenant context
    exists yet when `get_by_key` is called from an anonymous request);
    `create`'s caller already knows and supplies tenant_id explicitly."""

    async def get_by_key(self, share_key: str) -> PublicShareLink | None: ...
    async def get_by_resource(
        self, resource_type: ShareableResourceType, resource_id: UUID
    ) -> PublicShareLink | None:
        """Existing key for a resource, if it was ever made public before
        — reused on re-toggle rather than minting a new key (see
        PublicShareLink's own docstring)."""
        ...
    async def create(self, link: PublicShareLink) -> PublicShareLink: ...
