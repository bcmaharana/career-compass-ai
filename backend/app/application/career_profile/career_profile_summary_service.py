"""Cheap counts snapshot of one profile (Master or a Target Role Profile).

Reuses every existing per-domain service's own `list_for_current_user`
(now target_role_id-aware) rather than adding new repository-level COUNT
queries — same reuse pattern ClearCareerProfileService already established
for the reverse (deletion) direction. Volumes here are small (a handful of
items per profile), so counting an already-fetched list is simpler than a
separate SQL COUNT path for no real performance cost.
"""

from __future__ import annotations

from uuid import UUID

from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.domain.career_profile.entities import CareerProfileSummary


class CareerProfileSummaryService:
    def __init__(
        self,
        career_profiles: CareerProfileService,
        experiences: ExperienceService,
        educations: EducationService,
        certifications: CertificationService,
        career_highlights: CareerHighlightService,
        key_achievements: KeyAchievementService,
    ) -> None:
        self._career_profiles = career_profiles
        self._experiences = experiences
        self._educations = educations
        self._certifications = certifications
        self._career_highlights = career_highlights
        self._key_achievements = key_achievements

    async def get_summary(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> CareerProfileSummary:
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        experiences = await self._experiences.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        educations = await self._educations.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        certifications = await self._certifications.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        career_highlights = await self._career_highlights.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        key_achievements = await self._key_achievements.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        return CareerProfileSummary(
            experience_count=len(experiences),
            education_count=len(educations),
            certification_count=len(certifications),
            career_highlight_count=len(career_highlights),
            key_achievement_count=len(key_achievements),
            competency_count=len(profile.core_competencies),
            has_headline=bool(profile.headline),
            has_summary=bool(profile.summary),
        )
