"""ProfileSkill application service. Follows the same ownership-check
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
from app.domain.career_profile.entities import ProfileSkill
from app.domain.career_profile.repositories import Direction, ProfileSkillRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.entities import PublicShareLink
from app.domain.showcase_page.repositories import PublicShareLinkRepository

MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024
_SKILL_FILE_TYPES = {
    "application/pdf": (b"%PDF-", ".pdf"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
}
logger = get_logger(__name__)
_BADGE_FILE_TYPES = {
    "image/jpeg": _SKILL_FILE_TYPES["image/jpeg"],
    "image/png": _SKILL_FILE_TYPES["image/png"],
}


class ProfileSkillService:
    def __init__(
        self,
        skills: ProfileSkillRepository,
        career_profiles: CareerProfileService,
        share_links: PublicShareLinkRepository | None = None,
        storage: PrivateObjectStorageRepository | None = None,
    ) -> None:
        self._skills = skills
        self._career_profiles = career_profiles
        self._share_links = share_links
        self._storage = storage

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, skill_id: UUID
    ) -> ProfileSkill:
        skill = await self._skills.get_by_id(tenant_id, skill_id)
        if skill is None:
            raise NotFoundError("Skill not found.", code="PROFILE_SKILL_NOT_FOUND")
        profile = await self._career_profiles.get_by_id(
            tenant_id=tenant_id, profile_id=skill.career_profile_id
        )
        if profile is None or profile.user_id != user_id:
            raise NotFoundError("Skill not found.", code="PROFILE_SKILL_NOT_FOUND")
        return skill

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
        target_role_id: UUID | None = None,
        badge_url: str | None = None,
    ) -> ProfileSkill:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        return await self._skills.create(
            ProfileSkill(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                name=name,
                issuing_organization=issuing_organization,
                issue_date=issue_date,
                expiration_date=expiration_date,
                credential_id=credential_id,
                credential_url=credential_url,
                skill_file_key=None,
                skill_file_name=None,
                skill_file_content_type=None,
                badge_image_key=None,
                badge_image_name=None,
                badge_image_content_type=None,
                badge_url=badge_url,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> list[ProfileSkill]:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return await self._skills.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        skill_id: UUID,
        name: str,
        issuing_organization: str,
        issue_date: date | None,
        expiration_date: date | None,
        credential_id: str | None,
        credential_url: str | None,
        include_in_resume: bool = True,
        badge_url: str | None = None,
        update_badge_url: bool = False,
    ) -> ProfileSkill:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        skill.name = name
        skill.issuing_organization = issuing_organization
        skill.issue_date = issue_date
        skill.expiration_date = expiration_date
        skill.credential_id = credential_id
        skill.credential_url = credential_url
        if update_badge_url:
            skill.badge_url = badge_url or None
        skill.include_in_resume = include_in_resume
        return await self._skills.update(skill)

    async def upload_file(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        skill_id: UUID,
        file_kind: str,
        filename: str,
        content: bytes,
    ) -> ProfileSkill:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        allowed_types = _SKILL_FILE_TYPES if file_kind == "skill" else _BADGE_FILE_TYPES
        matched_type = next(
            (
                (content_type, extension)
                for content_type, (signature, extension) in allowed_types.items()
                if content.startswith(signature)
            ),
            None,
        )
        if matched_type is None:
            accepted = "PDF, JPG, or PNG" if file_kind == "skill" else "JPG or PNG"
            raise ValidationError(f"Upload a valid {accepted} file.")
        if not content or len(content) > MAX_SKILL_FILE_SIZE:
            raise ValidationError("Files must be no larger than 10 MB.")

        content_type, extension = matched_type
        safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        safe_filename = safe_filename[:240] or f"{file_kind}{extension}"
        key = f"career-profile-skills/{tenant_id}/{user_id}/{skill.id}/{uuid.uuid4()}{extension}"
        if self._storage is None:
            raise RuntimeError("Private skill storage is not configured.")
        await self._storage.upload_private(key=key, content=content, content_type=content_type)

        if file_kind == "skill":
            previous_key = skill.skill_file_key
            skill.skill_file_key = key
            skill.skill_file_name = safe_filename
            skill.skill_file_content_type = content_type
        else:
            previous_key = skill.badge_image_key
            skill.badge_image_key = key
            skill.badge_image_name = safe_filename
            skill.badge_image_content_type = content_type
        updated = await self._skills.update(skill)
        if previous_key:
            try:
                await self._storage.delete_private(key=previous_key)
            except CareerCompassError:
                logger.warning("skill_replaced_file_cleanup_failed", key=previous_key)
        return updated

    async def delete_file(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        skill_id: UUID,
        file_kind: str,
    ) -> None:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        if file_kind == "skill":
            key = skill.skill_file_key
            skill.skill_file_key = None
            skill.skill_file_name = None
            skill.skill_file_content_type = None
        else:
            key = skill.badge_image_key
            skill.badge_image_key = None
            skill.badge_image_name = None
            skill.badge_image_content_type = None
        await self._skills.update(skill)
        if key and self._storage is None:
            raise RuntimeError("Private skill storage is not configured.")
        if key and self._storage is not None:
            await self._storage.delete_private(key=key)

    async def get_file_url(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        skill_id: UUID,
        file_kind: str,
    ) -> str:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        key = skill.skill_file_key if file_kind == "skill" else skill.badge_image_key
        if key is None:
            raise NotFoundError("Skill file not found.", code="SKILL_FILE_NOT_FOUND")
        if self._storage is None:
            raise RuntimeError("Private skill storage is not configured.")
        return await self._storage.get_presigned_url(
            key=key,
            expires_in_seconds=300,
            disposition="inline",
        )

    async def get_or_create_share_link(
        self, *, tenant_id: UUID, user_id: UUID, skill_id: UUID
    ) -> str:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        if self._share_links is None:
            raise RuntimeError("Public skill sharing is not configured.")
        link = await self._share_links.get_by_resource("profile_skill", skill.id)
        if link is not None:
            return link.share_key
        link = PublicShareLink(
            share_key=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            resource_type="profile_skill",
            resource_id=skill.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        return (await self._share_links.create(link)).share_key

    async def get_existing_share_key(self, skill_id: UUID) -> str | None:
        if self._share_links is None:
            return None
        link = await self._share_links.get_by_resource("profile_skill", skill_id)
        return link.share_key if link is not None else None

    async def revoke_share_link(self, *, tenant_id: UUID, user_id: UUID, skill_id: UUID) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, skill_id=skill_id)
        await self._delete_share_link(skill_id)

    async def _delete_share_link(self, skill_id: UUID) -> None:
        if self._share_links is not None:
            await self._share_links.delete_by_resource("profile_skill", skill_id)

    async def _cleanup_files(self, skill: ProfileSkill) -> None:
        keys = (skill.skill_file_key, skill.badge_image_key)
        if any(keys) and self._storage is None:
            raise RuntimeError("Private skill storage is not configured.")
        if self._storage is None:
            return
        for key in keys:
            if key is None:
                continue
            try:
                await self._storage.delete_private(key=key)
            except CareerCompassError:
                logger.warning("skill_file_cleanup_failed", key=key)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, skill_id: UUID) -> None:
        skill = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, skill_id=skill_id
        )
        await self._skills.soft_delete(tenant_id, skill_id)
        await self._delete_share_link(skill_id)
        await self._cleanup_files(skill)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, skill_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, skill_id=skill_id)
        await self._skills.move(tenant_id, skill_id, direction)

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        skills = await self._skills.list_for_profile(tenant_id, profile.id)
        await self._skills.soft_delete_all_for_profile(tenant_id, profile.id)
        for skill in skills:
            await self._delete_share_link(skill.id)
            await self._cleanup_files(skill)
