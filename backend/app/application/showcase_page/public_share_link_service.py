"""Mints (or reuses) the unguessable share key that is the entire access
-control boundary for a public Showcase Page or public Interview Prep
Topic ("Article"). Shared by ShowcasePageService.set_public and
InterviewTopicService's own public-toggle so this logic — including the
lazy handle assignment a public URL's first path segment depends on —
isn't duplicated per resource type.

A resource is only ever issued one key for its whole lifetime (see
PublicShareLink's own docstring) — get_or_create_key reuses the existing
row on every later re-toggle rather than minting a new one, which is why
this is framed as "get or create" rather than a bare "create".
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from app.application.identity.handle_service import HandleService
from app.domain.showcase_page.entities import PublicShareLink, ShareableResourceType
from app.domain.showcase_page.repositories import PublicShareLinkRepository

#: 24 random bytes, base64url-encoded — far too large to brute-force,
#: same order of magnitude as password_reset_tokens' own raw token.
_SHARE_KEY_BYTES = 24


class PublicShareLinkService:
    def __init__(self, links: PublicShareLinkRepository, handles: HandleService) -> None:
        self._links = links
        self._handles = handles

    async def get_or_create_key(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        resource_type: ShareableResourceType,
        resource_id: UUID,
    ) -> str:
        existing = await self._links.get_by_resource(resource_type, resource_id)
        if existing is not None:
            return existing.share_key

        # Assigning a handle is a prerequisite for the resource being
        # reachable at all (it's the first path segment of the public
        # URL), so it happens here, lazily, the first time ANY resource
        # is actually made public — not eagerly at signup or profile
        # save. ensure_handle is a no-op if the user already has one.
        await self._handles.ensure_handle(tenant_id=tenant_id, user_id=user_id)

        link = PublicShareLink(
            share_key=secrets.token_urlsafe(_SHARE_KEY_BYTES),
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        return (await self._links.create(link)).share_key

    async def get_existing_key(
        self, *, resource_type: ShareableResourceType, resource_id: UUID
    ) -> str | None:
        """Read-only lookup for display purposes (e.g. showing a
        resource's current public URL on a GET, not just right after a
        toggle) — never mints a new key, unlike get_or_create_key."""
        link = await self._links.get_by_resource(resource_type, resource_id)
        return link.share_key if link is not None else None
