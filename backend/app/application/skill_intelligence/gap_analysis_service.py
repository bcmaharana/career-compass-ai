"""Gap analysis application service (Phase 3, simplified per ADR-005).

Computes, for each of the user's target roles, which of that role's
`required_skills` aren't present (case-insensitively) in the user's
`CareerProfile.core_competencies`. Both are plain free-text lists — the
catalog/proficiency/category model (Skill, SkillCategory, UserSkill,
RoleTag) that this originally blended against was removed entirely, so
there's no more catalog-driven "core gaps" half.

Pure computation — no new storage, just cross-referencing the
career_profile domain's two existing services.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.target_role_service import TargetRoleService


@dataclass(slots=True)
class TargetRoleGap:
    target_role_id: UUID
    role_name: str
    tag: str
    missing_skills: list[str]


@dataclass(slots=True)
class GapAnalysisResult:
    target_role_gaps: list[TargetRoleGap]


class GapAnalysisService:
    def __init__(
        self,
        career_profiles: CareerProfileService,
        target_roles: TargetRoleService,
    ) -> None:
        self._career_profiles = career_profiles
        self._target_roles = target_roles

    async def compute(self, *, tenant_id: UUID, user_id: UUID) -> GapAnalysisResult:
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        owned = {competency.lower() for competency in profile.core_competencies}

        target_roles = await self._target_roles.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id
        )
        target_role_gaps: list[TargetRoleGap] = []
        for role in target_roles:
            missing = [skill for skill in role.required_skills if skill.lower() not in owned]
            if not missing:
                continue
            target_role_gaps.append(
                TargetRoleGap(
                    target_role_id=role.id,
                    role_name=role.role_name,
                    tag=role.tag,
                    missing_skills=missing,
                )
            )

        return GapAnalysisResult(target_role_gaps=target_role_gaps)
