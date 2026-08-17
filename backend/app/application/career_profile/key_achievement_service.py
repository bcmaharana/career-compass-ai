"""Key achievement application service. Follows the same
ownership-check pattern as ExperienceService — see that module's
docstring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.core.rich_text import sanitize_rich_text
from app.domain.career_profile.entities import KeyAchievement
from app.domain.career_profile.repositories import Direction, KeyAchievementRepository


class KeyAchievementService:
    def __init__(
        self,
        achievements: KeyAchievementRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._achievements = achievements
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, achievement_id: UUID
    ) -> KeyAchievement:
        achievement = await self._achievements.get_by_id(tenant_id, achievement_id)
        if achievement is None:
            raise NotFoundError("Key achievement not found.", code="KEY_ACHIEVEMENT_NOT_FOUND")
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=achievement.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
            raise NotFoundError("Key achievement not found.", code="KEY_ACHIEVEMENT_NOT_FOUND")
        return achievement

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
    ) -> KeyAchievement:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._achievements.create(
            KeyAchievement(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                title=title,
                company=company,
                description=sanitize_rich_text(description),
                occurred_on=occurred_on,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> list[KeyAchievement]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return await self._achievements.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        achievement_id: UUID,
        title: str,
        company: str | None,
        description: str | None,
        occurred_on: date | None,
        include_in_resume: bool = True,
    ) -> KeyAchievement:
        achievement = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, achievement_id=achievement_id
        )
        achievement.title = title
        achievement.company = company
        achievement.description = sanitize_rich_text(description)
        achievement.occurred_on = occurred_on
        achievement.include_in_resume = include_in_resume
        return await self._achievements.update(achievement)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, achievement_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, achievement_id=achievement_id
        )
        await self._achievements.soft_delete(tenant_id, achievement_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, achievement_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, achievement_id=achievement_id
        )
        await self._achievements.move(tenant_id, achievement_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._achievements.soft_delete_all_for_profile(tenant_id, profile.id)
