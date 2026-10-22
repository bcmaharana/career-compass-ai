"""Certification application service. Follows the same ownership-check
pattern as ExperienceService — see that module's docstring.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.career_profile.entities import Certification
from app.domain.career_profile.repositories import CertificationRepository, Direction
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.entities import PublicShareLink
from app.domain.showcase_page.repositories import PublicShareLinkRepository

MAX_CERTIFICATE_FILE_SIZE = 10 * 1024 * 1024
_CERTIFICATE_FILE_TYPES = {
    "application/pdf": (b"%PDF-", ".pdf"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
}
logger = get_logger(__name__)
_BADGE_FILE_TYPES = {
    "image/jpeg": _CERTIFICATE_FILE_TYPES["image/jpeg"],
    "image/png": _CERTIFICATE_FILE_TYPES["image/png"],
}


class CertificationService:
    def __init__(
        self,
        certifications: CertificationRepository,
        career_profiles: CareerProfileService,
        share_links: PublicShareLinkRepository | None = None,
        storage: PrivateObjectStorageRepository | None = None,
    ) -> None:
        self._certifications = certifications
        self._career_profiles = career_profiles
        self._share_links = share_links
        self._storage = storage

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID
    ) -> Certification:
        certification = await self._certifications.get_by_id(tenant_id, certification_id)
        if certification is None:
            raise NotFoundError("Certification not found.", code="CERTIFICATION_NOT_FOUND")
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=certification.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
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
        does_not_expire: bool = False,
        target_role_id: UUID | None = None,
        badge_url: str | None = None,
    ) -> Certification:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._certifications.create(
            Certification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                name=name,
                issuing_organization=issuing_organization,
                issue_date=issue_date,
                expiration_date=None if does_not_expire else expiration_date,
                credential_id=credential_id,
                credential_url=credential_url,
                certificate_file_key=None,
                certificate_file_name=None,
                certificate_file_content_type=None,
                badge_image_key=None,
                badge_image_name=None,
                badge_image_content_type=None,
                badge_url=badge_url,
                does_not_expire=does_not_expire,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> list[Certification]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
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
        does_not_expire: bool = False,
        include_in_resume: bool = True,
        badge_url: str | None = None,
        update_badge_url: bool = False,
    ) -> Certification:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        certification.name = name
        certification.issuing_organization = issuing_organization
        certification.issue_date = issue_date
        certification.expiration_date = None if does_not_expire else expiration_date
        certification.does_not_expire = does_not_expire
        certification.credential_id = credential_id
        certification.credential_url = credential_url
        if update_badge_url:
            certification.badge_url = badge_url or None
        certification.include_in_resume = include_in_resume
        return await self._certifications.update(certification)

    async def upload_file(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        certification_id: UUID,
        file_kind: str,
        filename: str,
        content: bytes,
    ) -> Certification:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        allowed_types = _CERTIFICATE_FILE_TYPES if file_kind == "certificate" else _BADGE_FILE_TYPES
        matched_type = next(
            (
                (content_type, extension)
                for content_type, (signature, extension) in allowed_types.items()
                if content.startswith(signature)
            ),
            None,
        )
        if matched_type is None:
            accepted = "PDF, JPG, or PNG" if file_kind == "certificate" else "JPG or PNG"
            raise ValidationError(f"Upload a valid {accepted} file.")
        if not content or len(content) > MAX_CERTIFICATE_FILE_SIZE:
            raise ValidationError("Files must be no larger than 10 MB.")

        content_type, extension = matched_type
        safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        safe_filename = safe_filename[:240] or f"{file_kind}{extension}"
        key = (
            f"certificates/{tenant_id}/{user_id}/{certification.id}/"
            f"{uuid.uuid4()}{extension}"
        )
        if self._storage is None:
            raise RuntimeError("Private certificate storage is not configured.")
        await self._storage.upload_private(key=key, content=content, content_type=content_type)

        if file_kind == "certificate":
            previous_key = certification.certificate_file_key
            certification.certificate_file_key = key
            certification.certificate_file_name = safe_filename
            certification.certificate_file_content_type = content_type
        else:
            previous_key = certification.badge_image_key
            certification.badge_image_key = key
            certification.badge_image_name = safe_filename
            certification.badge_image_content_type = content_type
        updated = await self._certifications.update(certification)
        if previous_key:
            try:
                await self._storage.delete_private(key=previous_key)
            except CareerCompassError:
                logger.warning("certification_replaced_file_cleanup_failed", key=previous_key)
        return updated

    async def delete_file(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        certification_id: UUID,
        file_kind: str,
    ) -> None:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        if file_kind == "certificate":
            key = certification.certificate_file_key
            certification.certificate_file_key = None
            certification.certificate_file_name = None
            certification.certificate_file_content_type = None
        else:
            key = certification.badge_image_key
            certification.badge_image_key = None
            certification.badge_image_name = None
            certification.badge_image_content_type = None
        await self._certifications.update(certification)
        if key and self._storage is None:
            raise RuntimeError("Private certificate storage is not configured.")
        if key and self._storage is not None:
            await self._storage.delete_private(key=key)

    async def get_file_url(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        certification_id: UUID,
        file_kind: str,
    ) -> str:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        key = (
            certification.certificate_file_key
            if file_kind == "certificate"
            else certification.badge_image_key
        )
        if key is None:
            raise NotFoundError("Certificate file not found.", code="CERTIFICATE_FILE_NOT_FOUND")
        if self._storage is None:
            raise RuntimeError("Private certificate storage is not configured.")
        return await self._storage.get_presigned_url(
            key=key,
            expires_in_seconds=300,
            disposition="inline",
        )

    async def get_or_create_share_link(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID
    ) -> str:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        if self._share_links is None:
            raise RuntimeError("Public certificate sharing is not configured.")
        link = await self._share_links.get_by_resource("certification", certification.id)
        if link is not None:
            return link.share_key
        link = PublicShareLink(
            share_key=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            resource_type="certification",
            resource_id=certification.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        return (await self._share_links.create(link)).share_key

    async def get_existing_share_key(self, certification_id: UUID) -> str | None:
        if self._share_links is None:
            return None
        link = await self._share_links.get_by_resource("certification", certification_id)
        return link.share_key if link is not None else None

    async def revoke_share_link(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        await self._delete_share_link(certification_id)

    async def _delete_share_link(self, certification_id: UUID) -> None:
        if self._share_links is not None:
            await self._share_links.delete_by_resource("certification", certification_id)

    async def _cleanup_files(self, certification: Certification) -> None:
        keys = (certification.certificate_file_key, certification.badge_image_key)
        if any(keys) and self._storage is None:
            raise RuntimeError("Private certificate storage is not configured.")
        if self._storage is None:
            return
        for key in keys:
            if key is None:
                continue
            try:
                await self._storage.delete_private(key=key)
            except CareerCompassError:
                logger.warning("certification_file_cleanup_failed", key=key)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID) -> None:
        certification = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        await self._certifications.soft_delete(tenant_id, certification_id)
        await self._delete_share_link(certification_id)
        await self._cleanup_files(certification)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, certification_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, certification_id=certification_id
        )
        await self._certifications.move(tenant_id, certification_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        certifications = await self._certifications.list_for_profile(tenant_id, profile.id)
        await self._certifications.soft_delete_all_for_profile(tenant_id, profile.id)
        for certification in certifications:
            await self._delete_share_link(certification.id)
            await self._cleanup_files(certification)
