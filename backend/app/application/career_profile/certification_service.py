"""Certification application service. Follows the same ownership-check
pattern as ExperienceService — see that module's docstring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import Certification
from app.domain.career_profile.repositories import CertificationRepository, Direction


class CertificationService:
    def __init__(
        self,
        certifications: CertificationRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._certifications = certifications
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID
    ) -> Certification:
        certification = await self._certifications.get_by_id(tenant_id, certification_id)
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        if certification is None or certification.career_profile_id != profile.id:
            raise NotFoundError("Certification not found.", code="CERTIFICATION_NOT_FOUND")
        return certification

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        issuing_organization: str,
        issue_date: date | None,
        expiration_date: date | None,
        credential_id: str | None,
        credential_url: str | None,
    ) -> Certification:
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        now = datetime.now(UTC)
        return await self._certifications.create(
            Certification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                name=name,
                issuing_organization=issuing_organization,
                issue_date=issue_date,
                expiration_date=expiration_date,
                credential_id=credential_id,
                credential_url=credential_url,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID
    ) -> list[Certification]:
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        return await self._certifications.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        certification_id: UUID,
        name: str,
        issuing_organization: str,
        issue_date: date | None,
        expiration_date: date | None,
        credential_id: str | None,
        credential_url: str | None,
    ) -> Certification:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        certification.name = name
        certification.issuing_organization = issuing_organization
        certification.issue_date = issue_date
        certification.expiration_date = expiration_date
        certification.credential_id = credential_id
        certification.credential_url = credential_url
        return await self._certifications.update(certification)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        await self._certifications.soft_delete(tenant_id, certification_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        await self._certifications.move(tenant_id, certification_id, direction)
