"""Target role application service (UI enhancement brief Part 2.5).

Up to 10 target roles per user — a Right Nav widget on the Career Profile
page, not a page section. Ownership check follows the same
not-found-not-forbidden reasoning as CareerGoalService.

`required_skills` (add/remove methods below) replaced the skill_intelligence
domain's catalog-linked TargetRoleSkill rows — see ADR-005. It's a plain
free-text list living directly on TargetRole, the same shape as
CareerProfile.core_competencies, matched case-insensitively for dedup.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import TargetRole
from app.domain.career_profile.repositories import TargetRoleRepository

MAX_TARGET_ROLES = 10


class TargetRoleService:
    def __init__(self, target_roles: TargetRoleRepository) -> None:
        self._target_roles = target_roles

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> TargetRole:
        """Public (not the usual leading-underscore ownership-check
        helper): other domains' services need this to verify a target
        role before attaching their own data to it — see
        skill_intelligence's TargetRoleSkillService, which follows the
        same cross-domain-via-the-other-service's-public-method pattern
        CareerHighlightService already uses with
        CareerProfileService.get_or_create.
        """
        target_role = await self._target_roles.get_by_id(tenant_id, target_role_id)
        if target_role is None or target_role.user_id != user_id:
            raise NotFoundError("Target role not found.", code="TARGET_ROLE_NOT_FOUND")
        return target_role

    async def list_for_current_user(self, *, tenant_id: UUID, user_id: UUID) -> list[TargetRole]:
        return await self._target_roles.list_for_user(tenant_id, user_id)

    async def add(
        self, *, tenant_id: UUID, user_id: UUID, role_name: str, tag: str
    ) -> TargetRole:
        existing = await self._target_roles.list_for_user(tenant_id, user_id)
        if len(existing) >= MAX_TARGET_ROLES:
            raise ValidationError(
                f"You can only have up to {MAX_TARGET_ROLES} target roles.",
                code="TARGET_ROLE_LIMIT_REACHED",
            )
        return await self._target_roles.create(
            TargetRole(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                role_name=role_name,
                tag=tag.upper(),
                created_at=datetime.now(UTC),
            )
        )

    async def update(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, role_name: str, tag: str
    ) -> TargetRole:
        target_role = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        target_role.role_name = role_name
        target_role.tag = tag.upper()
        return await self._target_roles.update(target_role)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID) -> None:
        await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._target_roles.soft_delete(tenant_id, target_role_id)

    async def add_required_skill(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, name: str
    ) -> TargetRole:
        target_role = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        trimmed = name.strip()
        if not trimmed:
            raise ValidationError(
                "Skill name is required.", code="REQUIRED_SKILL_NAME_REQUIRED"
            )
        if not any(s.lower() == trimmed.lower() for s in target_role.required_skills):
            target_role.required_skills = [*target_role.required_skills, trimmed]
            target_role = await self._target_roles.update(target_role)
        return target_role

    async def remove_required_skill(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, name: str
    ) -> TargetRole:
        target_role = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        target_role.required_skills = [
            s for s in target_role.required_skills if s.lower() != name.lower()
        ]
        return await self._target_roles.update(target_role)

    async def rename_required_skill(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, old_name: str, new_name: str
    ) -> TargetRole:
        target_role = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        trimmed = new_name.strip()
        if not trimmed:
            raise ValidationError(
                "Skill name is required.", code="REQUIRED_SKILL_NAME_REQUIRED"
            )
        if any(
            s.lower() == trimmed.lower() and s.lower() != old_name.lower()
            for s in target_role.required_skills
        ):
            raise ValidationError(
                "That skill is already required for this role.",
                code="REQUIRED_SKILL_ALREADY_EXISTS",
            )
        target_role.required_skills = [
            trimmed if s.lower() == old_name.lower() else s for s in target_role.required_skills
        ]
        return await self._target_roles.update(target_role)
