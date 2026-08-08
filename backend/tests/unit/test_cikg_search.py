"""Unit tests for CIKG search infrastructure (Phase 4.5.1 MVP 2A):
EmbeddingIndexingService's stale-detection and SearchService's hybrid
fusion/ranking and graceful degradation.

Fakes return copies on fetch, not live object references — same
discipline as tests/unit/test_career_intelligence.py.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.career_intelligence.embedding_service import EmbeddingIndexingService
from app.application.career_intelligence.search_service import SearchService
from app.application.career_intelligence.skill_alias_resolution_service import (
    SkillAliasResolutionService,
)
from app.core.exceptions import CareerCompassError
from app.domain.career_intelligence.aliasing import normalize_alias_text
from app.domain.career_intelligence.entities import (
    CikgRole,
    Competency,
    ContentEmbedding,
    EmbeddableEntityType,
    EmbeddingModel,
    RelatedSkill,
    Skill,
    SkillAlias,
)


class FakeSkillRepository:
    def __init__(self, skills: list[Skill] | None = None) -> None:
        self.rows: dict[uuid.UUID, Skill] = {s.id: s for s in (skills or [])}

    async def create(self, skill: Skill) -> Skill:
        self.rows[skill.id] = skill
        return replace(skill)

    async def get_by_id(self, skill_id: uuid.UUID) -> Skill | None:
        row = self.rows.get(skill_id)
        return replace(row) if row else None

    async def get_by_name(self, name: str) -> Skill | None:
        for row in self.rows.values():
            if row.name == name:
                return replace(row)
        return None

    async def list_approved(self) -> list[Skill]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]

    async def update(self, skill: Skill) -> Skill:
        self.rows[skill.id] = skill
        return replace(skill)


class FakeCikgRoleRepository:
    async def create(self, role: CikgRole) -> CikgRole:  # pragma: no cover - unused here
        raise NotImplementedError

    async def get_by_id(self, role_id: uuid.UUID) -> CikgRole | None:
        return None

    async def get_by_title(self, title: str) -> CikgRole | None:
        return None

    async def list_approved(self) -> list[CikgRole]:
        return []

    async def update(self, role: CikgRole) -> CikgRole:  # pragma: no cover - unused here
        raise NotImplementedError


class FakeCompetencyRepository:
    async def create(self, competency: Competency) -> Competency:  # pragma: no cover
        raise NotImplementedError

    async def get_by_id(self, competency_id: uuid.UUID) -> Competency | None:
        return None

    async def get_by_name(self, name: str) -> Competency | None:
        return None

    async def list_approved(self) -> list[Competency]:
        return []

    async def update(self, competency: Competency) -> Competency:  # pragma: no cover
        raise NotImplementedError

    async def approve(self, competency_id: uuid.UUID) -> Competency:  # pragma: no cover
        raise NotImplementedError


class FakeEmbeddingModelRepository:
    def __init__(self, default_model: EmbeddingModel | None = None) -> None:
        self.rows: dict[uuid.UUID, EmbeddingModel] = {}
        if default_model is not None:
            self.rows[default_model.id] = default_model

    async def create(self, model: EmbeddingModel) -> EmbeddingModel:
        self.rows[model.id] = model
        return replace(model)

    async def get_by_model_name(self, model_name: str) -> EmbeddingModel | None:
        for row in self.rows.values():
            if row.model_name == model_name:
                return replace(row)
        return None

    async def get_default(self) -> EmbeddingModel | None:
        for row in self.rows.values():
            if row.is_default:
                return replace(row)
        return None


class FakeContentEmbeddingRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, ContentEmbedding] = {}

    async def upsert(self, embedding: ContentEmbedding) -> ContentEmbedding:
        for existing_id, existing in list(self.rows.items()):
            if (
                existing.entity_type == embedding.entity_type
                and existing.entity_id == embedding.entity_id
                and existing.embedding_model_id == embedding.embedding_model_id
            ):
                self.rows[existing_id] = embedding
                return replace(embedding)
        self.rows[embedding.id] = embedding
        return replace(embedding)

    async def get_by_entity(
        self, entity_type: EmbeddableEntityType, entity_id: uuid.UUID, embedding_model_id: uuid.UUID
    ) -> ContentEmbedding | None:
        for row in self.rows.values():
            if (
                row.entity_type == entity_type
                and row.entity_id == entity_id
                and row.embedding_model_id == embedding_model_id
            ):
                return replace(row)
        return None

    async def list_hashes_for_type(
        self, entity_type: EmbeddableEntityType, embedding_model_id: uuid.UUID
    ) -> dict[uuid.UUID, str]:
        return {
            row.entity_id: row.source_text_hash
            for row in self.rows.values()
            if row.entity_type == entity_type and row.embedding_model_id == embedding_model_id
        }


class FakeEmbeddingProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[list[str]] = []

    async def embed(self, *, texts: list[str], model_name: str) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.should_fail:
            raise CareerCompassError("embedding provider unreachable", code="AI_PROVIDER_ERROR")
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRelatedSkillRepository:
    def __init__(self, edges: list[RelatedSkill] | None = None) -> None:
        self.edges = edges or []

    async def create(self, edge: RelatedSkill) -> RelatedSkill:  # pragma: no cover
        raise NotImplementedError

    async def get_by_pair(
        self, skill_a_id: uuid.UUID, skill_b_id: uuid.UUID
    ) -> RelatedSkill | None:  # pragma: no cover
        return None

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[RelatedSkill]:
        return [e for e in self.edges if e.skill_a_id == skill_id or e.skill_b_id == skill_id]

    async def approve(self, edge_id: uuid.UUID) -> RelatedSkill:  # pragma: no cover
        raise NotImplementedError


class FakeSkillAliasRepository:
    def __init__(self, aliases: list[SkillAlias] | None = None) -> None:
        self.rows = {a.id: a for a in (aliases or [])}

    async def create(self, alias: SkillAlias) -> SkillAlias:  # pragma: no cover
        raise NotImplementedError

    async def get_by_normalized_text(self, normalized_text: str) -> SkillAlias | None:
        for row in self.rows.values():
            if row.normalized_text == normalized_text:
                return replace(row)
        return None

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SkillAlias]:  # pragma: no cover
        return [replace(r) for r in self.rows.values() if r.skill_id == skill_id]


class FakeSearchRepository:
    def __init__(
        self,
        *,
        fulltext_results: dict[EmbeddableEntityType, list[tuple[uuid.UUID, str, str | None, float]]]
        | None = None,
        vector_results: dict[EmbeddableEntityType, list[tuple[uuid.UUID, float]]] | None = None,
        names: dict[uuid.UUID, tuple[str, str | None]] | None = None,
        relationship_counts: dict[uuid.UUID, int] | None = None,
        category_skill_ids: set[uuid.UUID] | None = None,
        role_skill_ids: set[uuid.UUID] | None = None,
    ) -> None:
        self._fulltext = fulltext_results or {}
        self._vector = vector_results or {}
        self._names = names or {}
        self._relationship_counts = relationship_counts or {}
        self._category_skill_ids = category_skill_ids or set()
        self._role_skill_ids = role_skill_ids or set()

    async def fulltext_search(
        self, entity_type: EmbeddableEntityType, query: str, *, limit: int
    ) -> list[tuple[uuid.UUID, str, str | None, float]]:
        return self._fulltext.get(entity_type, [])[:limit]

    async def vector_search(
        self,
        entity_type: EmbeddableEntityType,
        query_embedding: list[float],
        embedding_model_id: uuid.UUID,
        *,
        limit: int,
    ) -> list[tuple[uuid.UUID, float]]:
        return self._vector.get(entity_type, [])[:limit]

    async def get_names(
        self, entity_type: EmbeddableEntityType, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, str | None]]:
        return {eid: self._names[eid] for eid in entity_ids if eid in self._names}

    async def relationship_count(self, entity_type: EmbeddableEntityType, entity_id: uuid.UUID) -> int:
        return self._relationship_counts.get(entity_id, 0)

    async def filter_skill_ids_by_category(self, category_id: uuid.UUID) -> set[uuid.UUID]:
        return self._category_skill_ids

    async def filter_skill_ids_by_role(self, role_id: uuid.UUID) -> set[uuid.UUID]:
        return self._role_skill_ids


def _skill(name: str, description: str | None = "a description") -> Skill:
    now = datetime.now(UTC)
    return Skill(
        id=uuid.uuid4(),
        name=name,
        description=description,
        content_status="approved",
        source_attribution="seed_script",
        created_at=now,
        updated_at=now,
    )


def _related_edge(skill_a: uuid.UUID, skill_b: uuid.UUID) -> RelatedSkill:
    return RelatedSkill(
        id=uuid.uuid4(),
        skill_a_id=skill_a,
        skill_b_id=skill_b,
        strength="moderate",
        content_status="approved",
        source_attribution="seed_script",
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestEmbeddingIndexingService:
    async def test_first_run_embeds_every_approved_skill(self) -> None:
        skills = FakeSkillRepository([_skill("Python Programming"), _skill("Data Analysis")])
        provider = FakeEmbeddingProvider()
        service = EmbeddingIndexingService(
            provider,
            FakeEmbeddingModelRepository(),
            FakeContentEmbeddingRepository(),
            skills,
            FakeCikgRoleRepository(),
            FakeCompetencyRepository(),
            model_name="nomic-embed-text",
            provider_name="ollama",
            dimensions=3,
        )

        counts = await service.reindex_all()

        assert counts["skill"] == 2
        assert len(provider.calls) == 1
        assert len(provider.calls[0]) == 2

    async def test_second_run_is_a_no_op_when_nothing_changed(self) -> None:
        skills = FakeSkillRepository([_skill("Python Programming")])
        provider = FakeEmbeddingProvider()
        content_embeddings = FakeContentEmbeddingRepository()
        embedding_models = FakeEmbeddingModelRepository()
        service = EmbeddingIndexingService(
            provider,
            embedding_models,
            content_embeddings,
            skills,
            FakeCikgRoleRepository(),
            FakeCompetencyRepository(),
            model_name="nomic-embed-text",
            provider_name="ollama",
            dimensions=3,
        )
        await service.reindex_all()

        counts = await service.reindex_all()

        assert counts["skill"] == 0
        assert len(provider.calls) == 1  # no second embed call at all

    async def test_changed_description_triggers_reembed_of_only_that_skill(self) -> None:
        skill = _skill("Python Programming", description="original")
        skills = FakeSkillRepository([skill, _skill("Data Analysis")])
        provider = FakeEmbeddingProvider()
        service = EmbeddingIndexingService(
            provider,
            FakeEmbeddingModelRepository(),
            FakeContentEmbeddingRepository(),
            skills,
            FakeCikgRoleRepository(),
            FakeCompetencyRepository(),
            model_name="nomic-embed-text",
            provider_name="ollama",
            dimensions=3,
        )
        await service.reindex_all()
        skills.rows[skill.id].description = "changed description"

        counts = await service.reindex_all()

        assert counts["skill"] == 1
        assert len(provider.calls) == 2
        assert provider.calls[1] == ["Python Programming. changed description"]


def _make_search_service(
    search_repo: FakeSearchRepository,
    *,
    related_skills: FakeRelatedSkillRepository | None = None,
    embedding_models: FakeEmbeddingModelRepository | None = None,
    embedding_provider: FakeEmbeddingProvider | None = None,
    aliases: FakeSkillAliasRepository | None = None,
    skills_for_alias: FakeSkillRepository | None = None,
) -> SearchService:
    alias_resolver = SkillAliasResolutionService(
        aliases or FakeSkillAliasRepository(), skills_for_alias or FakeSkillRepository()
    )
    return SearchService(
        search_repo,
        related_skills or FakeRelatedSkillRepository(),
        embedding_models or FakeEmbeddingModelRepository(),
        embedding_provider or FakeEmbeddingProvider(),
        alias_resolver,
    )


@pytest.mark.unit
class TestSearchServiceFusion:
    async def test_graph_match_ranks_above_fulltext_and_vector_only_matches(self) -> None:
        resolved = _skill("Data Analysis")
        graph_neighbor = _skill("Python Programming")
        fulltext_only = _skill("Statistical Modeling")
        vector_only = _skill("Machine Learning")

        skills_for_alias = FakeSkillRepository([resolved])
        aliases = FakeSkillAliasRepository(
            [
                SkillAlias(
                    id=uuid.uuid4(),
                    skill_id=resolved.id,
                    alias_text="Data Analysis",
                    normalized_text=normalize_alias_text("Data Analysis"),
                    source="curated",
                    confidence=None,
                    created_at=datetime.now(UTC),
                )
            ]
        )
        related_skills = FakeRelatedSkillRepository([_related_edge(resolved.id, graph_neighbor.id)])
        search_repo = FakeSearchRepository(
            fulltext_results={
                "skill": [(fulltext_only.id, fulltext_only.name, fulltext_only.description, 0.9)]
            },
            vector_results={"skill": [(vector_only.id, 0.95)]},
            names={
                graph_neighbor.id: (graph_neighbor.name, graph_neighbor.description),
                vector_only.id: (vector_only.name, vector_only.description),
            },
        )
        embedding_models = FakeEmbeddingModelRepository(
            EmbeddingModel(
                id=uuid.uuid4(),
                provider="ollama",
                model_name="nomic-embed-text",
                dimensions=3,
                is_default=True,
                created_at=datetime.now(UTC),
            )
        )
        service = _make_search_service(
            search_repo,
            related_skills=related_skills,
            embedding_models=embedding_models,
            aliases=aliases,
            skills_for_alias=skills_for_alias,
        )

        results = await service.search(query="Data Analysis")

        assert results[0].entity_id == graph_neighbor.id
        assert results[0].matched_via == ["graph"]
        # the fulltext-only and vector-only hits still surface, just lower
        result_ids = [r.entity_id for r in results]
        assert fulltext_only.id in result_ids
        assert vector_only.id in result_ids

    async def test_degrades_gracefully_when_embedding_provider_fails(self) -> None:
        fulltext_hit = _skill("Objection Handling")
        search_repo = FakeSearchRepository(
            fulltext_results={
                "skill": [(fulltext_hit.id, fulltext_hit.name, fulltext_hit.description, 0.5)]
            },
        )
        embedding_models = FakeEmbeddingModelRepository(
            EmbeddingModel(
                id=uuid.uuid4(),
                provider="ollama",
                model_name="nomic-embed-text",
                dimensions=3,
                is_default=True,
                created_at=datetime.now(UTC),
            )
        )
        service = _make_search_service(
            search_repo,
            embedding_models=embedding_models,
            embedding_provider=FakeEmbeddingProvider(should_fail=True),
        )

        results = await service.search(query="handling customer objections")

        assert len(results) == 1
        assert results[0].entity_id == fulltext_hit.id

    async def test_no_embedding_model_indexed_skips_vector_step_silently(self) -> None:
        fulltext_hit = _skill("Objection Handling")
        search_repo = FakeSearchRepository(
            fulltext_results={
                "skill": [(fulltext_hit.id, fulltext_hit.name, fulltext_hit.description, 0.5)]
            },
        )
        service = _make_search_service(search_repo, embedding_models=FakeEmbeddingModelRepository())

        results = await service.search(query="handling customer objections")

        assert len(results) == 1

    async def test_category_filter_excludes_non_matching_skills(self) -> None:
        in_category = _skill("Python Programming")
        outside_category = _skill("Welding")
        search_repo = FakeSearchRepository(
            fulltext_results={
                "skill": [
                    (in_category.id, in_category.name, in_category.description, 0.8),
                    (outside_category.id, outside_category.name, outside_category.description, 0.9),
                ]
            },
            category_skill_ids={in_category.id},
        )
        service = _make_search_service(search_repo)

        results = await service.search(query="skill", category_id=uuid.uuid4())

        result_ids = {r.entity_id for r in results}
        assert result_ids == {in_category.id}

    async def test_relationship_count_boosts_ranking_among_equal_relevance(self) -> None:
        richly_connected = _skill("Python Programming")
        isolated = _skill("Quantum Computing")
        search_repo = FakeSearchRepository(
            fulltext_results={
                "skill": [
                    (richly_connected.id, richly_connected.name, richly_connected.description, 0.5),
                    (isolated.id, isolated.name, isolated.description, 0.5),
                ]
            },
            relationship_counts={richly_connected.id: 10, isolated.id: 0},
        )
        service = _make_search_service(search_repo)

        results = await service.search(query="skill")

        assert results[0].entity_id == richly_connected.id
        assert results[0].score > results[1].score
