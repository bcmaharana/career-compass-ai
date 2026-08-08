"""Read-oriented CIKG queries — the product-facing (approved-only) half
of the content governance workflow.

One class for now rather than cikg-api-boundaries.md's eventual
skill_service.py/role_service.py-per-entity split: MVP 1's read surface
is plain list/get with no filtering, ranking, or search yet (that's
MVP 2A, cikg-semantic-search.md) — splitting into one file per entity
now would be premature given how little each one does. Revisit the
split once search/filtering complexity actually arrives.

Every `get_*` treats non-approved content as not found — per
cikg-content-governance.md, "only approved content is visible to
search, gap analysis, AI grounding, or any other read path outside the
governance/curation tooling itself." Curator tooling that needs to see
a draft goes through ContentGovernanceService instead, which has no
such filter.
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.career_intelligence.entities import (
    CategoryParent,
    CikgRole,
    Competency,
    RelatedSkill,
    RoleRequiredSkill,
    Skill,
    SkillAlias,
    SkillCategory,
    SkillCategoryMembership,
)
from app.domain.career_intelligence.repositories import (
    CategoryParentRepository,
    CikgRoleRepository,
    CompetencyRepository,
    RelatedSkillRepository,
    RoleRequiredSkillRepository,
    SkillAliasRepository,
    SkillCategoryMembershipRepository,
    SkillCategoryRepository,
    SkillRepository,
)


class CatalogQueryService:
    def __init__(
        self,
        categories: SkillCategoryRepository,
        competencies: CompetencyRepository,
        skills: SkillRepository,
        roles: CikgRoleRepository,
        category_parents: CategoryParentRepository,
        skill_category_memberships: SkillCategoryMembershipRepository,
        related_skills: RelatedSkillRepository,
        role_required_skills: RoleRequiredSkillRepository,
        aliases: SkillAliasRepository,
    ) -> None:
        self._categories = categories
        self._competencies = competencies
        self._skills = skills
        self._roles = roles
        self._category_parents = category_parents
        self._skill_category_memberships = skill_category_memberships
        self._related_skills = related_skills
        self._role_required_skills = role_required_skills
        self._aliases = aliases

    async def list_categories(self) -> list[SkillCategory]:
        return await self._categories.list_approved()

    async def get_category(self, category_id: UUID) -> SkillCategory:
        category = await self._categories.get_by_id(category_id)
        if category is None or category.content_status != "approved":
            raise NotFoundError("Skill category not found.", code="SKILL_CATEGORY_NOT_FOUND")
        return category

    async def list_category_parents(self, category_id: UUID) -> list[CategoryParent]:
        return await self._category_parents.list_parents(category_id)

    async def list_category_children(self, category_id: UUID) -> list[CategoryParent]:
        return await self._category_parents.list_children(category_id)

    async def list_competencies(self) -> list[Competency]:
        return await self._competencies.list_approved()

    async def list_skills(self) -> list[Skill]:
        return await self._skills.list_approved()

    async def get_skill(self, skill_id: UUID) -> Skill:
        skill = await self._skills.get_by_id(skill_id)
        if skill is None or skill.content_status != "approved":
            raise NotFoundError("Skill not found.", code="SKILL_NOT_FOUND")
        return skill

    async def list_skill_categories(self, skill_id: UUID) -> list[SkillCategoryMembership]:
        return await self._skill_category_memberships.list_for_skill(skill_id)

    async def list_related_skills(self, skill_id: UUID) -> list[RelatedSkill]:
        return await self._related_skills.list_for_skill(skill_id)

    async def list_skill_aliases(self, skill_id: UUID) -> list[SkillAlias]:
        return await self._aliases.list_for_skill(skill_id)

    async def list_roles(self) -> list[CikgRole]:
        return await self._roles.list_approved()

    async def get_role(self, role_id: UUID) -> CikgRole:
        role = await self._roles.get_by_id(role_id)
        if role is None or role.content_status != "approved":
            raise NotFoundError("Role not found.", code="CIKG_ROLE_NOT_FOUND")
        return role

    async def list_required_skills(self, role_id: UUID) -> list[RoleRequiredSkill]:
        return await self._role_required_skills.list_for_role(role_id)
