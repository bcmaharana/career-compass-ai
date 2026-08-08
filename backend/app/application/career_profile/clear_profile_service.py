"""Orchestrates a full Career Profile reset.

Reuses every existing per-domain service's own `clear_all` (or, for the
top-level CareerProfile fields, `update`) rather than duplicating any
deletion logic — same reuse pattern `ResumeMergeService` already
established for writing *into* a profile, just the reverse direction.
The profile photo is deliberately NOT touched here — see clear_all's
own docstring.
"""

from __future__ import annotations

from uuid import UUID

from app.application.career_profile.career_goal_service import CareerGoalService
from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.application.career_profile.peer_endorsement_service import PeerEndorsementService


class ClearCareerProfileService:
    def __init__(
        self,
        career_profiles: CareerProfileService,
        experiences: ExperienceService,
        educations: EducationService,
        certifications: CertificationService,
        career_highlights: CareerHighlightService,
        key_achievements: KeyAchievementService,
        peer_endorsements: PeerEndorsementService,
        career_goals: CareerGoalService,
    ) -> None:
        self._career_profiles = career_profiles
        self._experiences = experiences
        self._educations = educations
        self._certifications = certifications
        self._career_highlights = career_highlights
        self._key_achievements = key_achievements
        self._peer_endorsements = peer_endorsements
        self._career_goals = career_goals

    async def clear_all(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> None:
        """target_role_id=None clears Master: every domain fans out,
        including Career Goals/Peer Endorsements — but NOT the photo,
        by explicit request. A person's profile photo is treated as an
        identity element separate from the profile *content* a clear is
        meant to reset, so "Clear Career Profile" leaves it untouched;
        deleting the photo specifically is still its own dedicated
        action (DELETE /career-profile/photo). A real target_role_id
        clears only that Target Role Profile: Career Goals, Peer
        Endorsements, and the photo stay Master-only by design (resume
        merge never touches them, and a person has one photo/one set of
        goals, not one per role), so they're skipped entirely rather
        than being cleared alongside a target role's data.
        """
        await self._experiences.clear_all(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._educations.clear_all(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._certifications.clear_all(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._career_highlights.clear_all(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._key_achievements.clear_all(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )

        if target_role_id is None:
            await self._peer_endorsements.clear_all(tenant_id=tenant_id, user_id=user_id)
            await self._career_goals.clear_all(tenant_id=tenant_id, user_id=user_id)

        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._career_profiles.update(
            tenant_id=tenant_id,
            user_id=user_id,
            headline=None,
            summary=None,
            core_competencies=[],
            section_order=profile.section_order,
            target_role_id=target_role_id,
        )
