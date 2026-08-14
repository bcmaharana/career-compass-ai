"""Gap analysis application service (Phase 3, simplified per ADR-005).

Computes, for each of the user's target roles, which of that role's
`required_skills` (plain free-text list[str]) aren't present
(case-insensitively, by name) in the user's core competencies — the old
catalog/proficiency/category model (Skill, SkillCategory, UserSkill,
RoleTag) this originally blended against was removed entirely per
ADR-005, so there's no more catalog-driven "core gaps" half.

"Owned" skills are the *union* of the Master Profile's core_competencies
and that specific Target Role Profile's own core_competencies — Core
Competencies became a genuinely per-profile field once Target Role
Profiles were made fully independent (own Experience/Education/etc.,
not a filtered view of Master), but this service originally kept
reading only the Master profile regardless of which role it was
evaluating, silently ignoring anything a user added directly to a
Target Role Profile's own Core Competencies section. Fixed live after a
real user report: skills added under a specific target role's own Core
Competencies still showed as "missing" for that exact role. The union
(rather than switching to the target role's own list alone) keeps
existing Master-only usage unaffected — a target role profile nobody's
ever tailored competencies for just contributes an empty set.

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
        master_profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id
        )
        master_owned = {competency.name.lower() for competency in master_profile.core_competencies}

        target_roles = await self._target_roles.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id
        )
        target_role_gaps: list[TargetRoleGap] = []
        for role in target_roles:
            role_profile = await self._career_profiles.get_or_create(
                tenant_id=tenant_id, user_id=user_id, target_role_id=role.id
            )
            owned = master_owned | {
                competency.name.lower() for competency in role_profile.core_competencies
            }
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
