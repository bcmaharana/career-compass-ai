"""Education application service. Follows the same ownership-check
pattern as ExperienceService — see that module's docstring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import Education
from app.domain.career_profile.repositories import Direction, EducationRepository


class EducationService:
    def __init__(
        self,
        educations: EducationRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._educations = educations
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, education_id: UUID
    ) -> Education:
        education = await self._educations.get_by_id(tenant_id, education_id)
        if education is None:
            raise NotFoundError("Education not found.", code="EDUCATION_NOT_FOUND")
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=education.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
            raise NotFoundError("Education not found.", code="EDUCATION_NOT_FOUND")
        return education

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        institution: str,
        degree: str | None,
        field_of_study: str | None,
        start_date: date | None,
        end_date: date | None,
        description: str | None,
        target_role_id: UUID | None = None,
    ) -> Education:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._educations.create(
            Education(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                institution=institution,
                degree=degree,
                field_of_study=field_of_study,
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
    ) -> list[Education]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return await self._educations.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        education_id: UUID,
        institution: str,
        degree: str | None,
        field_of_study: str | None,
        start_date: date | None,
        end_date: date | None,
        description: str | None,
        include_in_resume: bool = True,
    ) -> Education:
        education = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, education_id=education_id
        )
        education.institution = institution
        education.degree = degree
        education.field_of_study = field_of_study
        education.start_date = start_date
        education.end_date = end_date
        education.description = description
        education.include_in_resume = include_in_resume
        return await self._educations.update(education)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, education_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, education_id=education_id
        )
        await self._educations.soft_delete(tenant_id, education_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, education_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, education_id=education_id
        )
        await self._educations.move(tenant_id, education_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._educations.soft_delete_all_for_profile(tenant_id, profile.id)
