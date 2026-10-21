"""Read-only public projection for individually shared skills."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.career_profile.entities import ProfileSkill
from app.domain.career_profile.repositories import CareerProfileRepository, ProfileSkillRepository
from app.domain.identity.repositories import TenantContextBinder, UserRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.repositories import PublicShareLinkRepository


@dataclass(frozen=True, slots=True)
class PublicProfileSkillView:
    profile_skill: ProfileSkill
    owner_display_name: str
    skill_file_url: str | None
    badge_image_url: str | None


class PublicProfileSkillService:
    def __init__(
        self,
        share_links: PublicShareLinkRepository,
        tenant_context: TenantContextBinder,
        profile_skills: ProfileSkillRepository,
        career_profiles: CareerProfileRepository,
        users: UserRepository,
        storage: PrivateObjectStorageRepository,
    ) -> None:
        self._share_links = share_links
        self._tenant_context = tenant_context
        self._profile_skills = profile_skills
        self._career_profiles = career_profiles
        self._users = users
        self._storage = storage

    async def get_skill(self, share_key: str) -> PublicProfileSkillView | None:
        link = await self._share_links.get_by_key(share_key)
        if link is None or link.resource_type != "profile_skill":
            return None

        await self._tenant_context.bind(link.tenant_id)
        profile_skill = await self._profile_skills.get_by_id(link.tenant_id, link.resource_id)
        if profile_skill is None:
            return None
        profile = await self._career_profiles.get_by_id(
            link.tenant_id, profile_skill.career_profile_id
        )
        if profile is None or profile.user_id != link.user_id:
            return None
        owner = await self._users.get_by_id(link.tenant_id, link.user_id)
        if owner is None:
            return None

        skill_file_url = None
        if profile_skill.skill_file_key:
            skill_file_url = await self._storage.get_presigned_url(
                key=profile_skill.skill_file_key,
                expires_in_seconds=300,
                disposition="inline",
            )

        badge_image_url = None
        if profile_skill.badge_image_key:
            badge_image_url = await self._storage.get_presigned_url(
                key=profile_skill.badge_image_key,
                expires_in_seconds=300,
                disposition="inline",
            )

        return PublicProfileSkillView(
            profile_skill=profile_skill,
            owner_display_name=owner.display_name,
            skill_file_url=skill_file_url,
            badge_image_url=badge_image_url,
        )
