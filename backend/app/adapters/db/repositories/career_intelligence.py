"""SQLAlchemy repository implementations for the Career Intelligence
Knowledge Graph (CIKG) bounded context.

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/career_profile.py. Every repository here
operates on global reference data via a plain (non-tenant-scoped)
AsyncSession — see app/adapters/db/models/career_intelligence.py's
module docstring for why these tables carry no tenant_id/RLS.

Phase 4.5.1 MVP 2B: `approve()` is gone from every repository here —
nothing writes to a live row except `ContentRevisionService` applying
an approved revision, via `create()` (new entity/edge) or `update()`
(editing an existing node — edges don't support in-place edits, see
that service's docstring).
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    CategoryParentModel,
    CikgRoleModel,
    CompetencyModel,
    PrerequisiteOfEdgeModel,
    RelatedSkillModel,
    RoleProgressesToEdgeModel,
    RoleRequiredSkillModel,
    SkillAliasModel,
    SkillCategoryMembershipModel,
    SkillCategoryModel,
    SkillCompetencyMembershipModel,
    SkillModel,
    SpecializesEdgeModel,
    SynonymOfEdgeModel,
)
from app.core.exceptions import NotFoundError
from app.domain.career_intelligence.entities import (
    AliasSource,
    CategoryParent,
    CikgRole,
    Competency,
    ContentStatus,
    PrerequisiteOfEdge,
    RelatedSkill,
    RelationshipStrength,
    RequirementLevel,
    RoleProgressesToEdge,
    RoleRequiredSkill,
    Skill,
    SkillAlias,
    SkillCategory,
    SkillCategoryMembership,
    SkillCompetencyMembership,
    SpecializesEdge,
    SynonymOfEdge,
)

# --- Literal-narrowing helpers ---
#
# Every *_status/strength/requirement_level/source column below is a plain
# str at the SQLAlchemy level but DB CHECK-constrained (see
# app/adapters/db/models/career_intelligence.py) to exactly the values its
# domain Literal type allows — these just name that trust once instead of
# a `# type: ignore[arg-type]` repeated at every mapping call site.


def _status(value: str) -> ContentStatus:
    return cast(ContentStatus, value)


def _strength(value: str) -> RelationshipStrength:
    return cast(RelationshipStrength, value)


def _requirement_level(value: str) -> RequirementLevel:
    return cast(RequirementLevel, value)


def _alias_source(value: str) -> AliasSource:
    return cast(AliasSource, value)


# --- Node mapping functions ---


def _category_to_domain(model: SkillCategoryModel) -> SkillCategory:
    return SkillCategory(
        id=model.id,
        name=model.name,
        description=model.description,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _competency_to_domain(model: CompetencyModel) -> Competency:
    return Competency(
        id=model.id,
        name=model.name,
        description=model.description,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _skill_to_domain(model: SkillModel) -> Skill:
    return Skill(
        id=model.id,
        name=model.name,
        description=model.description,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
        ats_keywords=list(model.ats_keywords),
        proficiency_level_definitions=(
            dict(model.proficiency_level_definitions)
            if model.proficiency_level_definitions is not None
            else None
        ),
    )


def _cikg_role_to_domain(model: CikgRoleModel) -> CikgRole:
    return CikgRole(
        id=model.id,
        title=model.title,
        description=model.description,
        experience_level=model.experience_level,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


# --- Edge mapping functions ---


def _category_parent_to_domain(model: CategoryParentModel) -> CategoryParent:
    return CategoryParent(
        id=model.id,
        child_category_id=model.child_category_id,
        parent_category_id=model.parent_category_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _skill_category_membership_to_domain(
    model: SkillCategoryMembershipModel,
) -> SkillCategoryMembership:
    return SkillCategoryMembership(
        id=model.id,
        skill_id=model.skill_id,
        category_id=model.category_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _skill_competency_membership_to_domain(
    model: SkillCompetencyMembershipModel,
) -> SkillCompetencyMembership:
    return SkillCompetencyMembership(
        id=model.id,
        skill_id=model.skill_id,
        competency_id=model.competency_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _related_skill_to_domain(model: RelatedSkillModel) -> RelatedSkill:
    return RelatedSkill(
        id=model.id,
        skill_a_id=model.skill_a_id,
        skill_b_id=model.skill_b_id,
        strength=_strength(model.strength),
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _role_required_skill_to_domain(model: RoleRequiredSkillModel) -> RoleRequiredSkill:
    return RoleRequiredSkill(
        id=model.id,
        role_id=model.role_id,
        skill_id=model.skill_id,
        requirement_level=_requirement_level(model.requirement_level),
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _skill_alias_to_domain(model: SkillAliasModel) -> SkillAlias:
    return SkillAlias(
        id=model.id,
        skill_id=model.skill_id,
        alias_text=model.alias_text,
        normalized_text=model.normalized_text,
        source=_alias_source(model.source),
        confidence=model.confidence,
        created_at=model.created_at,
    )


def _prerequisite_of_to_domain(model: PrerequisiteOfEdgeModel) -> PrerequisiteOfEdge:
    return PrerequisiteOfEdge(
        id=model.id,
        source_skill_id=model.source_skill_id,
        target_skill_id=model.target_skill_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _specializes_to_domain(model: SpecializesEdgeModel) -> SpecializesEdge:
    return SpecializesEdge(
        id=model.id,
        source_skill_id=model.source_skill_id,
        target_skill_id=model.target_skill_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


def _synonym_of_to_domain(model: SynonymOfEdgeModel) -> SynonymOfEdge:
    return SynonymOfEdge(
        id=model.id,
        skill_a_id=model.skill_a_id,
        skill_b_id=model.skill_b_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


# --- Node repositories ---


class SqlAlchemySkillCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, category: SkillCategory) -> SkillCategory:
        model = SkillCategoryModel(
            id=category.id,
            name=category.name,
            description=category.description,
            content_status=category.content_status,
            source_attribution=category.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _category_to_domain(model)

    async def update(self, category: SkillCategory) -> SkillCategory:
        model = await self._session.get(SkillCategoryModel, category.id)
        if model is None:
            raise NotFoundError("Skill category not found.", code="SKILL_CATEGORY_NOT_FOUND")
        model.name = category.name
        model.description = category.description
        model.content_status = category.content_status
        await self._session.flush()
        await self._session.refresh(model)
        return _category_to_domain(model)

    async def get_by_id(self, category_id: UUID) -> SkillCategory | None:
        result = await self._session.execute(
            select(SkillCategoryModel).where(
                SkillCategoryModel.id == category_id, SkillCategoryModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        return _category_to_domain(model) if model else None

    async def list_approved(self) -> list[SkillCategory]:
        result = await self._session.execute(
            select(SkillCategoryModel).where(
                SkillCategoryModel.content_status == "approved",
                SkillCategoryModel.deleted_at.is_(None),
            )
        )
        return [_category_to_domain(m) for m in result.scalars().all()]


class SqlAlchemyCompetencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, competency: Competency) -> Competency:
        model = CompetencyModel(
            id=competency.id,
            name=competency.name,
            description=competency.description,
            content_status=competency.content_status,
            source_attribution=competency.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _competency_to_domain(model)

    async def update(self, competency: Competency) -> Competency:
        model = await self._session.get(CompetencyModel, competency.id)
        if model is None:
            raise NotFoundError("Competency not found.", code="COMPETENCY_NOT_FOUND")
        model.name = competency.name
        model.description = competency.description
        model.content_status = competency.content_status
        await self._session.flush()
        await self._session.refresh(model)
        return _competency_to_domain(model)

    async def get_by_id(self, competency_id: UUID) -> Competency | None:
        result = await self._session.execute(
            select(CompetencyModel).where(
                CompetencyModel.id == competency_id, CompetencyModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        return _competency_to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Competency | None:
        result = await self._session.execute(
            select(CompetencyModel).where(
                CompetencyModel.name == name, CompetencyModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        return _competency_to_domain(model) if model else None

    async def list_approved(self) -> list[Competency]:
        result = await self._session.execute(
            select(CompetencyModel).where(
                CompetencyModel.content_status == "approved",
                CompetencyModel.deleted_at.is_(None),
            )
        )
        return [_competency_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, skill: Skill) -> Skill:
        model = SkillModel(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            ats_keywords=list(skill.ats_keywords),
            proficiency_level_definitions=skill.proficiency_level_definitions,
            content_status=skill.content_status,
            source_attribution=skill.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _skill_to_domain(model)

    async def update(self, skill: Skill) -> Skill:
        model = await self._session.get(SkillModel, skill.id)
        if model is None:
            raise NotFoundError("Skill not found.", code="SKILL_NOT_FOUND")
        model.name = skill.name
        model.description = skill.description
        model.ats_keywords = list(skill.ats_keywords)
        model.proficiency_level_definitions = skill.proficiency_level_definitions
        model.content_status = skill.content_status
        await self._session.flush()
        await self._session.refresh(model)
        return _skill_to_domain(model)

    async def get_by_id(self, skill_id: UUID) -> Skill | None:
        result = await self._session.execute(
            select(SkillModel).where(SkillModel.id == skill_id, SkillModel.deleted_at.is_(None))
        )
        model = result.scalar_one_or_none()
        return _skill_to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Skill | None:
        result = await self._session.execute(
            select(SkillModel).where(SkillModel.name == name, SkillModel.deleted_at.is_(None))
        )
        model = result.scalar_one_or_none()
        return _skill_to_domain(model) if model else None

    async def list_approved(self) -> list[Skill]:
        result = await self._session.execute(
            select(SkillModel).where(
                SkillModel.content_status == "approved", SkillModel.deleted_at.is_(None)
            )
        )
        return [_skill_to_domain(m) for m in result.scalars().all()]


class SqlAlchemyCikgRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, role: CikgRole) -> CikgRole:
        model = CikgRoleModel(
            id=role.id,
            title=role.title,
            description=role.description,
            experience_level=role.experience_level,
            content_status=role.content_status,
            source_attribution=role.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _cikg_role_to_domain(model)

    async def update(self, role: CikgRole) -> CikgRole:
        model = await self._session.get(CikgRoleModel, role.id)
        if model is None:
            raise NotFoundError("Role not found.", code="CIKG_ROLE_NOT_FOUND")
        model.title = role.title
        model.description = role.description
        model.experience_level = role.experience_level
        model.content_status = role.content_status
        await self._session.flush()
        await self._session.refresh(model)
        return _cikg_role_to_domain(model)

    async def get_by_id(self, role_id: UUID) -> CikgRole | None:
        result = await self._session.execute(
            select(CikgRoleModel).where(
                CikgRoleModel.id == role_id, CikgRoleModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        return _cikg_role_to_domain(model) if model else None

    async def get_by_title(self, title: str) -> CikgRole | None:
        result = await self._session.execute(
            select(CikgRoleModel).where(
                CikgRoleModel.title == title, CikgRoleModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        return _cikg_role_to_domain(model) if model else None

    async def list_approved(self) -> list[CikgRole]:
        result = await self._session.execute(
            select(CikgRoleModel).where(
                CikgRoleModel.content_status == "approved", CikgRoleModel.deleted_at.is_(None)
            )
        )
        return [_cikg_role_to_domain(m) for m in result.scalars().all()]


# --- Edge repositories ---


class SqlAlchemyCategoryParentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: CategoryParent) -> CategoryParent:
        model = CategoryParentModel(
            id=edge.id,
            child_category_id=edge.child_category_id,
            parent_category_id=edge.parent_category_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _category_parent_to_domain(model)

    async def list_all_approved(self) -> list[CategoryParent]:
        result = await self._session.execute(
            select(CategoryParentModel).where(CategoryParentModel.content_status == "approved")
        )
        return [_category_parent_to_domain(m) for m in result.scalars().all()]

    async def list_parents(self, child_category_id: UUID) -> list[CategoryParent]:
        result = await self._session.execute(
            select(CategoryParentModel).where(
                CategoryParentModel.child_category_id == child_category_id
            )
        )
        return [_category_parent_to_domain(m) for m in result.scalars().all()]

    async def list_children(self, parent_category_id: UUID) -> list[CategoryParent]:
        result = await self._session.execute(
            select(CategoryParentModel).where(
                CategoryParentModel.parent_category_id == parent_category_id
            )
        )
        return [_category_parent_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySkillCategoryMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: SkillCategoryMembership) -> SkillCategoryMembership:
        model = SkillCategoryMembershipModel(
            id=edge.id,
            skill_id=edge.skill_id,
            category_id=edge.category_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _skill_category_membership_to_domain(model)

    async def list_for_skill(self, skill_id: UUID) -> list[SkillCategoryMembership]:
        result = await self._session.execute(
            select(SkillCategoryMembershipModel).where(
                SkillCategoryMembershipModel.skill_id == skill_id
            )
        )
        return [_skill_category_membership_to_domain(m) for m in result.scalars().all()]

    async def list_for_category(self, category_id: UUID) -> list[SkillCategoryMembership]:
        result = await self._session.execute(
            select(SkillCategoryMembershipModel).where(
                SkillCategoryMembershipModel.category_id == category_id
            )
        )
        return [_skill_category_membership_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySkillCompetencyMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: SkillCompetencyMembership) -> SkillCompetencyMembership:
        model = SkillCompetencyMembershipModel(
            id=edge.id,
            skill_id=edge.skill_id,
            competency_id=edge.competency_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _skill_competency_membership_to_domain(model)

    async def list_for_skill(self, skill_id: UUID) -> list[SkillCompetencyMembership]:
        result = await self._session.execute(
            select(SkillCompetencyMembershipModel).where(
                SkillCompetencyMembershipModel.skill_id == skill_id
            )
        )
        return [_skill_competency_membership_to_domain(m) for m in result.scalars().all()]

    async def list_for_competency(self, competency_id: UUID) -> list[SkillCompetencyMembership]:
        result = await self._session.execute(
            select(SkillCompetencyMembershipModel).where(
                SkillCompetencyMembershipModel.competency_id == competency_id
            )
        )
        return [_skill_competency_membership_to_domain(m) for m in result.scalars().all()]


class SqlAlchemyRelatedSkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: RelatedSkill) -> RelatedSkill:
        model = RelatedSkillModel(
            id=edge.id,
            skill_a_id=edge.skill_a_id,
            skill_b_id=edge.skill_b_id,
            strength=edge.strength,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _related_skill_to_domain(model)

    async def get_by_pair(self, skill_a_id: UUID, skill_b_id: UUID) -> RelatedSkill | None:
        result = await self._session.execute(
            select(RelatedSkillModel).where(
                RelatedSkillModel.skill_a_id == skill_a_id,
                RelatedSkillModel.skill_b_id == skill_b_id,
            )
        )
        model = result.scalar_one_or_none()
        return _related_skill_to_domain(model) if model else None

    async def list_for_skill(self, skill_id: UUID) -> list[RelatedSkill]:
        result = await self._session.execute(
            select(RelatedSkillModel).where(
                (RelatedSkillModel.skill_a_id == skill_id)
                | (RelatedSkillModel.skill_b_id == skill_id)
            )
        )
        return [_related_skill_to_domain(m) for m in result.scalars().all()]


class SqlAlchemyRoleRequiredSkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: RoleRequiredSkill) -> RoleRequiredSkill:
        model = RoleRequiredSkillModel(
            id=edge.id,
            role_id=edge.role_id,
            skill_id=edge.skill_id,
            requirement_level=edge.requirement_level,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _role_required_skill_to_domain(model)

    async def list_for_role(self, role_id: UUID) -> list[RoleRequiredSkill]:
        result = await self._session.execute(
            select(RoleRequiredSkillModel).where(RoleRequiredSkillModel.role_id == role_id)
        )
        return [_role_required_skill_to_domain(m) for m in result.scalars().all()]

    async def list_for_skill(self, skill_id: UUID) -> list[RoleRequiredSkill]:
        result = await self._session.execute(
            select(RoleRequiredSkillModel).where(RoleRequiredSkillModel.skill_id == skill_id)
        )
        return [_role_required_skill_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySkillAliasRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, alias: SkillAlias) -> SkillAlias:
        model = SkillAliasModel(
            id=alias.id,
            skill_id=alias.skill_id,
            alias_text=alias.alias_text,
            normalized_text=alias.normalized_text,
            source=alias.source,
            confidence=alias.confidence,
        )
        self._session.add(model)
        await self._session.flush()
        return _skill_alias_to_domain(model)

    async def get_by_normalized_text(self, normalized_text: str) -> SkillAlias | None:
        result = await self._session.execute(
            select(SkillAliasModel).where(SkillAliasModel.normalized_text == normalized_text)
        )
        model = result.scalar_one_or_none()
        return _skill_alias_to_domain(model) if model else None

    async def list_for_skill(self, skill_id: UUID) -> list[SkillAlias]:
        result = await self._session.execute(
            select(SkillAliasModel).where(SkillAliasModel.skill_id == skill_id)
        )
        return [_skill_alias_to_domain(m) for m in result.scalars().all()]


class SqlAlchemyPrerequisiteOfEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: PrerequisiteOfEdge) -> PrerequisiteOfEdge:
        model = PrerequisiteOfEdgeModel(
            id=edge.id,
            source_skill_id=edge.source_skill_id,
            target_skill_id=edge.target_skill_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _prerequisite_of_to_domain(model)

    async def get_by_pair(
        self, source_skill_id: UUID, target_skill_id: UUID
    ) -> PrerequisiteOfEdge | None:
        result = await self._session.execute(
            select(PrerequisiteOfEdgeModel).where(
                PrerequisiteOfEdgeModel.source_skill_id == source_skill_id,
                PrerequisiteOfEdgeModel.target_skill_id == target_skill_id,
            )
        )
        model = result.scalar_one_or_none()
        return _prerequisite_of_to_domain(model) if model else None

    async def list_all_approved(self) -> list[PrerequisiteOfEdge]:
        result = await self._session.execute(
            select(PrerequisiteOfEdgeModel).where(
                PrerequisiteOfEdgeModel.content_status == "approved"
            )
        )
        return [_prerequisite_of_to_domain(m) for m in result.scalars().all()]

    async def list_for_skill(self, skill_id: UUID) -> list[PrerequisiteOfEdge]:
        result = await self._session.execute(
            select(PrerequisiteOfEdgeModel).where(
                (PrerequisiteOfEdgeModel.source_skill_id == skill_id)
                | (PrerequisiteOfEdgeModel.target_skill_id == skill_id)
            )
        )
        return [_prerequisite_of_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySpecializesEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: SpecializesEdge) -> SpecializesEdge:
        model = SpecializesEdgeModel(
            id=edge.id,
            source_skill_id=edge.source_skill_id,
            target_skill_id=edge.target_skill_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _specializes_to_domain(model)

    async def get_by_pair(
        self, source_skill_id: UUID, target_skill_id: UUID
    ) -> SpecializesEdge | None:
        result = await self._session.execute(
            select(SpecializesEdgeModel).where(
                SpecializesEdgeModel.source_skill_id == source_skill_id,
                SpecializesEdgeModel.target_skill_id == target_skill_id,
            )
        )
        model = result.scalar_one_or_none()
        return _specializes_to_domain(model) if model else None

    async def list_all_approved(self) -> list[SpecializesEdge]:
        result = await self._session.execute(
            select(SpecializesEdgeModel).where(SpecializesEdgeModel.content_status == "approved")
        )
        return [_specializes_to_domain(m) for m in result.scalars().all()]

    async def list_for_skill(self, skill_id: UUID) -> list[SpecializesEdge]:
        result = await self._session.execute(
            select(SpecializesEdgeModel).where(
                (SpecializesEdgeModel.source_skill_id == skill_id)
                | (SpecializesEdgeModel.target_skill_id == skill_id)
            )
        )
        return [_specializes_to_domain(m) for m in result.scalars().all()]


class SqlAlchemySynonymOfEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: SynonymOfEdge) -> SynonymOfEdge:
        model = SynonymOfEdgeModel(
            id=edge.id,
            skill_a_id=edge.skill_a_id,
            skill_b_id=edge.skill_b_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _synonym_of_to_domain(model)

    async def get_by_pair(self, skill_a_id: UUID, skill_b_id: UUID) -> SynonymOfEdge | None:
        result = await self._session.execute(
            select(SynonymOfEdgeModel).where(
                SynonymOfEdgeModel.skill_a_id == skill_a_id,
                SynonymOfEdgeModel.skill_b_id == skill_b_id,
            )
        )
        model = result.scalar_one_or_none()
        return _synonym_of_to_domain(model) if model else None

    async def list_for_skill(self, skill_id: UUID) -> list[SynonymOfEdge]:
        result = await self._session.execute(
            select(SynonymOfEdgeModel).where(
                (SynonymOfEdgeModel.skill_a_id == skill_id)
                | (SynonymOfEdgeModel.skill_b_id == skill_id)
            )
        )
        return [_synonym_of_to_domain(m) for m in result.scalars().all()]


def _role_progresses_to_domain(model: RoleProgressesToEdgeModel) -> RoleProgressesToEdge:
    return RoleProgressesToEdge(
        id=model.id,
        source_role_id=model.source_role_id,
        target_role_id=model.target_role_id,
        content_status=_status(model.content_status),
        source_attribution=model.source_attribution,
        created_at=model.created_at,
    )


class SqlAlchemyRoleProgressesToEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, edge: RoleProgressesToEdge) -> RoleProgressesToEdge:
        model = RoleProgressesToEdgeModel(
            id=edge.id,
            source_role_id=edge.source_role_id,
            target_role_id=edge.target_role_id,
            content_status=edge.content_status,
            source_attribution=edge.source_attribution,
        )
        self._session.add(model)
        await self._session.flush()
        return _role_progresses_to_domain(model)

    async def get_by_pair(
        self, source_role_id: UUID, target_role_id: UUID
    ) -> RoleProgressesToEdge | None:
        result = await self._session.execute(
            select(RoleProgressesToEdgeModel).where(
                RoleProgressesToEdgeModel.source_role_id == source_role_id,
                RoleProgressesToEdgeModel.target_role_id == target_role_id,
            )
        )
        model = result.scalar_one_or_none()
        return _role_progresses_to_domain(model) if model else None

    async def list_all_approved(self) -> list[RoleProgressesToEdge]:
        result = await self._session.execute(
            select(RoleProgressesToEdgeModel).where(
                RoleProgressesToEdgeModel.content_status == "approved"
            )
        )
        return [_role_progresses_to_domain(m) for m in result.scalars().all()]

    async def list_for_role(self, role_id: UUID) -> list[RoleProgressesToEdge]:
        result = await self._session.execute(
            select(RoleProgressesToEdgeModel).where(
                (RoleProgressesToEdgeModel.source_role_id == role_id)
                | (RoleProgressesToEdgeModel.target_role_id == role_id)
            )
        )
        return [_role_progresses_to_domain(m) for m in result.scalars().all()]
