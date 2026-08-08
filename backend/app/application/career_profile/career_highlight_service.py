"""Career highlight application service. Follows the same
ownership-check pattern as ExperienceService — see that module's
docstring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import CareerHighlight
from app.domain.career_profile.repositories import CareerHighlightRepository, Direction


class CareerHighlightService:
    def __init__(
        self,
        highlights: CareerHighlightRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._highlights = highlights
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, highlight_id: UUID
    ) -> CareerHighlight:
        highlight = await self._highlights.get_by_id(tenant_id, highlight_id)
        if highlight is None:
            raise NotFoundError("Career highlight not found.", code="CAREER_HIGHLIGHT_NOT_FOUND")
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=highlight.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
            raise NotFoundError("Career highlight not found.", code="CAREER_HIGHLIGHT_NOT_FOUND")
        return highlight

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        title: str,
        company: str | None,
        description: str | None,
        occurred_on: date | None,
        target_role_id: UUID | None = None,
    ) -> CareerHighlight:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._highlights.create(
            CareerHighlight(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                title=title,
                company=company,
                description=description,
                occurred_on=occurred_on,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> list[CareerHighlight]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return await self._highlights.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        highlight_id: UUID,
        title: str,
        company: str | None,
        description: str | None,
        occurred_on: date | None,
    ) -> CareerHighlight:
        highlight = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, highlight_id=highlight_id
        )
        highlight.title = title
        highlight.company = company
        highlight.description = description
        highlight.occurred_on = occurred_on
        return await self._highlights.update(highlight)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, highlight_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, highlight_id=highlight_id
        )
        await self._highlights.soft_delete(tenant_id, highlight_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, highlight_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, highlight_id=highlight_id
        )
        await self._highlights.move(tenant_id, highlight_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._highlights.soft_delete_all_for_profile(tenant_id, profile.id)
