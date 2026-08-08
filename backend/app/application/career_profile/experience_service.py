"""Experience application service.

Every mutation verifies the target experience belongs to the *caller's
own* career profile before proceeding — RLS (app/adapters/db) already
enforces tenant isolation, but experiences aren't scoped by user_id
directly (only by career_profile_id), so cross-user-within-the-same
-tenant access needs an explicit check here. A mismatch is reported as
NotFoundError, not ForbiddenError — this endpoint has no legitimate
reason to confirm "yes, that experience ID exists, it's just not yours,"
which would leak information about other users' data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import Experience
from app.domain.career_profile.repositories import Direction, ExperienceRepository


class ExperienceService:
    def __init__(
        self,
        experiences: ExperienceRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._experiences = experiences
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, experience_id: UUID
    ) -> Experience:
        experience = await self._experiences.get_by_id(tenant_id, experience_id)
        if experience is None:
            raise NotFoundError("Experience not found.", code="EXPERIENCE_NOT_FOUND")
        # Resolved from the item's OWN profile, not "the" (Master-by-default)
        # profile — an item living on a Target Role Profile must still
        # resolve here, or every edit/delete/move on it would 404.
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=experience.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
            raise NotFoundError("Experience not found.", code="EXPERIENCE_NOT_FOUND")
        return experience

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        title: str,
        company: str,
        location: str | None,
        start_date: date,
        end_date: date | None,
        description: str | None,
        target_role_id: UUID | None = None,
    ) -> Experience:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._experiences.create(
            Experience(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                title=title,
                company=company,
                location=location,
                start_date=start_date,
                end_date=end_date,
                description=description,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> list[Experience]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return await self._experiences.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        experience_id: UUID,
        title: str,
        company: str,
        location: str | None,
        start_date: date,
        end_date: date | None,
        description: str | None,
    ) -> Experience:
        experience = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, experience_id=experience_id
        )
        experience.title = title
        experience.company = company
        experience.location = location
        experience.start_date = start_date
        experience.end_date = end_date
        experience.description = description
        return await self._experiences.update(experience)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, experience_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, experience_id=experience_id
        )
        await self._experiences.soft_delete(tenant_id, experience_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, experience_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, experience_id=experience_id
        )
        await self._experiences.move(tenant_id, experience_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._experiences.soft_delete_all_for_profile(tenant_id, profile.id)
