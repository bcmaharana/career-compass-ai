"""Repository interfaces for the Career Intelligence Knowledge Graph
bounded context.

Application services depend only on these Protocols — see
app/domain/career_profile/repositories.py for the established pattern
this follows.

Phase 4.5.1 MVP 2B: nothing writes to a live node/edge row anymore
except an approved ContentRevision being applied
(content_revision_service.py) — MVP 1's per-entity `create()`-inserts-
draft-then-`approve()`-flips-status shape is gone. Node repositories
now expose `create()` (inserts at whatever content_status the caller
sets — always `"approved"` in practice, since nothing else calls it)
and `update()` (for editing an existing approved row in place — the
edit-with-history case). Edge repositories expose `create()` only —
editing an existing edge's metadata isn't supported in this slice;
proposing a materially different edge is a new edge, not an edit.
`list_approved` remains the product-facing read path.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.career_intelligence.entities import (
    CategoryParent,
    CikgRole,
    Competency,
    ContentEmbedding,
    ContentHistoryEntry,
    ContentRevision,
    EmbeddableEntityType,
    EmbeddingModel,
    PrerequisiteOfEdge,
    RelatedSkill,
    RoleRequiredSkill,
    Skill,
    SkillAlias,
    SkillCategory,
    SkillCategoryMembership,
    SkillCompetencyMembership,
    SpecializesEdge,
    SynonymOfEdge,
)


class SkillCategoryRepository(Protocol):
    """No `get_by_name` — category names are deliberately not unique
    (see SkillCategoryModel's docstring), so looking one up needs
    hierarchy context (parent), not just a name. Callers that need this
    (the MVP 1 seed script) query it directly, disambiguating via
    category_parents.
    """

    async def create(self, category: SkillCategory) -> SkillCategory: ...
    async def update(self, category: SkillCategory) -> SkillCategory: ...
    async def get_by_id(self, category_id: UUID) -> SkillCategory | None: ...
    async def list_approved(self) -> list[SkillCategory]: ...


class CompetencyRepository(Protocol):
    async def create(self, competency: Competency) -> Competency: ...
    async def update(self, competency: Competency) -> Competency: ...
    async def get_by_id(self, competency_id: UUID) -> Competency | None: ...
    async def get_by_name(self, name: str) -> Competency | None: ...
    async def list_approved(self) -> list[Competency]: ...


class SkillRepository(Protocol):
    async def create(self, skill: Skill) -> Skill: ...
    async def update(self, skill: Skill) -> Skill: ...
    async def get_by_id(self, skill_id: UUID) -> Skill | None: ...
    async def get_by_name(self, name: str) -> Skill | None: ...
    async def list_approved(self) -> list[Skill]: ...


class CikgRoleRepository(Protocol):
    async def create(self, role: CikgRole) -> CikgRole: ...
    async def update(self, role: CikgRole) -> CikgRole: ...
    async def get_by_id(self, role_id: UUID) -> CikgRole | None: ...
    async def get_by_title(self, title: str) -> CikgRole | None: ...
    async def list_approved(self) -> list[CikgRole]: ...


class CategoryParentRepository(Protocol):
    async def create(self, edge: CategoryParent) -> CategoryParent: ...
    async def list_all_approved(self) -> list[CategoryParent]: ...
    async def list_parents(self, child_category_id: UUID) -> list[CategoryParent]: ...
    async def list_children(self, parent_category_id: UUID) -> list[CategoryParent]: ...


class SkillCategoryMembershipRepository(Protocol):
    async def create(self, edge: SkillCategoryMembership) -> SkillCategoryMembership: ...
    async def list_for_skill(self, skill_id: UUID) -> list[SkillCategoryMembership]: ...
    async def list_for_category(self, category_id: UUID) -> list[SkillCategoryMembership]: ...


class SkillCompetencyMembershipRepository(Protocol):
    async def create(self, edge: SkillCompetencyMembership) -> SkillCompetencyMembership: ...
    async def list_for_skill(self, skill_id: UUID) -> list[SkillCompetencyMembership]: ...
    async def list_for_competency(
        self, competency_id: UUID
    ) -> list[SkillCompetencyMembership]: ...


class RelatedSkillRepository(Protocol):
    async def create(self, edge: RelatedSkill) -> RelatedSkill: ...
    async def get_by_pair(self, skill_a_id: UUID, skill_b_id: UUID) -> RelatedSkill | None: ...
    async def list_for_skill(self, skill_id: UUID) -> list[RelatedSkill]: ...


class RoleRequiredSkillRepository(Protocol):
    async def create(self, edge: RoleRequiredSkill) -> RoleRequiredSkill: ...
    async def list_for_role(self, role_id: UUID) -> list[RoleRequiredSkill]: ...
    async def list_for_skill(self, skill_id: UUID) -> list[RoleRequiredSkill]: ...


class SkillAliasRepository(Protocol):
    async def create(self, alias: SkillAlias) -> SkillAlias: ...
    async def get_by_normalized_text(self, normalized_text: str) -> SkillAlias | None: ...
    async def list_for_skill(self, skill_id: UUID) -> list[SkillAlias]: ...


# --- Search (Phase 4.5.1 MVP 2A) ---


class EmbeddingModelRepository(Protocol):
    async def create(self, model: EmbeddingModel) -> EmbeddingModel: ...
    async def get_by_model_name(self, model_name: str) -> EmbeddingModel | None: ...
    async def get_default(self) -> EmbeddingModel | None: ...


class ContentEmbeddingRepository(Protocol):
    async def upsert(self, embedding: ContentEmbedding) -> ContentEmbedding:
        """Insert or replace the row for (entity_type, entity_id,
        embedding_model_id) — content re-embeds in place, it never
        accumulates stale rows for the same entity+model pair."""
        ...

    async def get_by_entity(
        self, entity_type: EmbeddableEntityType, entity_id: UUID, embedding_model_id: UUID
    ) -> ContentEmbedding | None: ...

    async def list_hashes_for_type(
        self, entity_type: EmbeddableEntityType, embedding_model_id: UUID
    ) -> dict[UUID, str]:
        """entity_id -> source_text_hash for every existing embedding of
        this type/model — lets EmbeddingIndexingService diff against
        current content in one query rather than one per entity."""
        ...


class SearchRepository(Protocol):
    """The raw hybrid-search queries SearchService composes. Modeled as
    a Protocol (like every other repository here) so SearchService's
    fusion/ranking logic is unit-testable with a fake, even though the
    concrete implementation (SqlAlchemySearchRepository) is direct SQL
    rather than ORM-mapped dataclasses — see that class's docstring.
    """

    async def fulltext_search(
        self, entity_type: EmbeddableEntityType, query: str, *, limit: int
    ) -> list[tuple[UUID, str, str | None, float]]: ...

    async def vector_search(
        self,
        entity_type: EmbeddableEntityType,
        query_embedding: list[float],
        embedding_model_id: UUID,
        *,
        limit: int,
    ) -> list[tuple[UUID, float]]: ...

    async def get_names(
        self, entity_type: EmbeddableEntityType, entity_ids: list[UUID]
    ) -> dict[UUID, tuple[str, str | None]]: ...

    async def relationship_count(self, entity_type: EmbeddableEntityType, entity_id: UUID) -> int: ...

    async def filter_skill_ids_by_category(self, category_id: UUID) -> set[UUID]: ...

    async def filter_skill_ids_by_role(self, role_id: UUID) -> set[UUID]: ...


# --- Governance (Phase 4.5.1 MVP 2B) ---


class ContentRevisionRepository(Protocol):
    async def create(self, revision: ContentRevision) -> ContentRevision: ...
    async def update(self, revision: ContentRevision) -> ContentRevision:
        """Persists a status/review-field transition (submit/approve/
        reject/mark_rejected) — never touches `proposed_data` itself,
        which is immutable once a revision is created."""
        ...

    async def get_by_id(self, revision_id: UUID) -> ContentRevision | None: ...
    async def list_by_batch(self, import_batch_id: UUID) -> list[ContentRevision]: ...
    async def list_by_status(self, status: str) -> list[ContentRevision]: ...
    async def count_for_entity(self, entity_type: str, entity_id: UUID) -> int:
        """Existing revision count for this entity — the next
        `revision_number` is this plus one."""
        ...


class ContentHistoryRepository(Protocol):
    async def create(self, entry: ContentHistoryEntry) -> ContentHistoryEntry: ...
    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> list[ContentHistoryEntry]: ...


class PrerequisiteOfEdgeRepository(Protocol):
    async def create(self, edge: PrerequisiteOfEdge) -> PrerequisiteOfEdge: ...
    async def get_by_pair(
        self, source_skill_id: UUID, target_skill_id: UUID
    ) -> PrerequisiteOfEdge | None: ...
    async def list_all_approved(self) -> list[PrerequisiteOfEdge]: ...
    async def list_for_skill(self, skill_id: UUID) -> list[PrerequisiteOfEdge]: ...


class SpecializesEdgeRepository(Protocol):
    async def create(self, edge: SpecializesEdge) -> SpecializesEdge: ...
    async def get_by_pair(
        self, source_skill_id: UUID, target_skill_id: UUID
    ) -> SpecializesEdge | None: ...
    async def list_all_approved(self) -> list[SpecializesEdge]: ...
    async def list_for_skill(self, skill_id: UUID) -> list[SpecializesEdge]: ...


class SynonymOfEdgeRepository(Protocol):
    async def create(self, edge: SynonymOfEdge) -> SynonymOfEdge: ...
    async def get_by_pair(self, skill_a_id: UUID, skill_b_id: UUID) -> SynonymOfEdge | None: ...
    async def list_for_skill(self, skill_id: UUID) -> list[SynonymOfEdge]: ...
