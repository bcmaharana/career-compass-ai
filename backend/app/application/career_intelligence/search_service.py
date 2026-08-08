"""Hybrid search over CIKG content (Phase 4.5.1 MVP 2A) — implements
cikg-semantic-search.md's 3-signal design (graph traversal, vector
similarity, full-text) plus a live-computed `knowledge_quality_score`
ranking weight.

Follows the exact algorithm from cikg-semantic-search.md's "Worked
Example: Find all skills related to Product Strategy":
1. Resolve the query to a canonical `Skill` (reuses the existing
   `SkillAliasResolutionService` — same resolution ADR-006 §3 already
   uses elsewhere).
2. If resolved, traverse its approved `related_to` edges directly
   (reuses the existing `RelatedSkillRepository` from MVP 1) — exact,
   curated, ranks highest.
3. Full-text (`ts_rank` via `SearchRepository.fulltext_search`).
4. Vector similarity via `SearchRepository.vector_search` — **degrades
   gracefully** (skipped, not an error) if no embedding model has been
   indexed yet or the embedding provider call fails, mirroring
   `ChatService`'s existing "provider failure degrades, never 500s"
   precedent.
5. `category_id`/`role_id` (only meaningful for `skill` results) are
   applied as a hard post-filter, not blended into the score.
6. Every surviving result is weighted by a live-computed
   `knowledge_quality_score` — MVP 2A's deliberately simple version
   (`approval_status` is implicit, since only approved content is ever
   searched at all; `relationship_count` only). Source-authorship and
   usage/freshness/conflict factors are explicitly deferred (see
   cikg-semantic-search.md) — the former has no real signal yet, since
   every MVP 1 seed row shares `source_attribution="seed_script"`.
"""

from __future__ import annotations

from uuid import UUID

from app.ai_platform.embeddings.provider_interface import EmbeddingProviderInterface
from app.application.career_intelligence.skill_alias_resolution_service import (
    SkillAliasResolutionService,
)
from app.core.exceptions import CareerCompassError
from app.domain.career_intelligence.entities import EmbeddableEntityType, SearchResult
from app.domain.career_intelligence.repositories import (
    EmbeddingModelRepository,
    RelatedSkillRepository,
    SearchRepository,
)

_ALL_ENTITY_TYPES: tuple[EmbeddableEntityType, ...] = ("skill", "cikg_role", "competency")
_GRAPH_MATCH_SCORE = 2.0  # always outranks fulltext/vector scores (both are <= ~1.0)
_MAX_RELATIONSHIP_QUALITY_BONUS = 0.2
_OVER_FETCH_MULTIPLIER = 3


class SearchService:
    def __init__(
        self,
        search_repo: SearchRepository,
        related_skills: RelatedSkillRepository,
        embedding_models: EmbeddingModelRepository,
        embedding_provider: EmbeddingProviderInterface,
        alias_resolver: SkillAliasResolutionService,
    ) -> None:
        self._search_repo = search_repo
        self._related_skills = related_skills
        self._embedding_models = embedding_models
        self._embedding_provider = embedding_provider
        self._alias_resolver = alias_resolver

    async def search(
        self,
        *,
        query: str,
        entity_type: EmbeddableEntityType | None = None,
        category_id: UUID | None = None,
        role_id: UUID | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        # category_id/role_id only ever filter Skill results (a category
        # groups skills; a role requires skills) — restricting the
        # search scope to "skill" when either is given, regardless of
        # the requested entity_type, keeps the filter meaningful rather
        # than silently returning zero cikg_role/competency results.
        types_to_search: tuple[EmbeddableEntityType, ...]
        if category_id is not None or role_id is not None:
            types_to_search = ("skill",)
        elif entity_type is not None:
            types_to_search = (entity_type,)
        else:
            types_to_search = _ALL_ENTITY_TYPES

        results: dict[tuple[EmbeddableEntityType, UUID], SearchResult] = {}

        if "skill" in types_to_search:
            await self._add_graph_matches(query, results)

        for et in types_to_search:
            for entity_id, name, description, rank in await self._search_repo.fulltext_search(
                et, query, limit=limit * _OVER_FETCH_MULTIPLIER
            ):
                self._add_or_tag(results, et, entity_id, name, description, rank, "fulltext")

        await self._add_vector_matches(query, types_to_search, limit, results)

        if category_id is not None:
            allowed = await self._search_repo.filter_skill_ids_by_category(category_id)
            results = {k: v for k, v in results.items() if k[0] != "skill" or k[1] in allowed}
        if role_id is not None:
            allowed = await self._search_repo.filter_skill_ids_by_role(role_id)
            results = {k: v for k, v in results.items() if k[0] != "skill" or k[1] in allowed}

        weighted: list[SearchResult] = []
        for (et, entity_id), result in results.items():
            quality = await self._quality_multiplier(et, entity_id)
            result.score *= quality
            weighted.append(result)

        weighted.sort(key=lambda r: r.score, reverse=True)
        return weighted[:limit]

    async def _add_graph_matches(
        self, query: str, results: dict[tuple[EmbeddableEntityType, UUID], SearchResult]
    ) -> None:
        resolved = await self._alias_resolver.resolve(query)
        if resolved is None:
            return
        edges = await self._related_skills.list_for_skill(resolved.id)
        neighbor_ids = [
            edge.skill_b_id if edge.skill_a_id == resolved.id else edge.skill_a_id
            for edge in edges
            if edge.content_status == "approved"
        ]
        if not neighbor_ids:
            return
        names = await self._search_repo.get_names("skill", neighbor_ids)
        for neighbor_id in neighbor_ids:
            hit = names.get(neighbor_id)
            if hit is None:
                continue
            name, description = hit
            self._add_or_tag(
                results, "skill", neighbor_id, name, description, _GRAPH_MATCH_SCORE, "graph"
            )

    async def _add_vector_matches(
        self,
        query: str,
        types_to_search: tuple[EmbeddableEntityType, ...],
        limit: int,
        results: dict[tuple[EmbeddableEntityType, UUID], SearchResult],
    ) -> None:
        embedding_model = await self._embedding_models.get_default()
        if embedding_model is None:
            return  # no embeddings indexed yet — full-text/graph only
        try:
            vectors = await self._embedding_provider.embed(
                texts=[query], model_name=embedding_model.model_name
            )
        except CareerCompassError:
            return  # provider unreachable/erroring — degrade, don't fail the search
        query_vector = vectors[0]

        for et in types_to_search:
            hits = await self._search_repo.vector_search(
                et, query_vector, embedding_model.id, limit=limit * _OVER_FETCH_MULTIPLIER
            )
            missing_ids = [entity_id for entity_id, _ in hits if (et, entity_id) not in results]
            names = await self._search_repo.get_names(et, missing_ids) if missing_ids else {}
            for entity_id, similarity in hits:
                if (et, entity_id) in results:
                    self._tag_only(results, et, entity_id, "vector")
                    continue
                hit = names.get(entity_id)
                if hit is None:
                    continue
                name, description = hit
                self._add_or_tag(results, et, entity_id, name, description, similarity, "vector")

    async def _quality_multiplier(self, entity_type: EmbeddableEntityType, entity_id: UUID) -> float:
        relationship_count = await self._search_repo.relationship_count(entity_type, entity_id)
        bonus = min(relationship_count * 0.02, _MAX_RELATIONSHIP_QUALITY_BONUS)
        return 1.0 + bonus

    @staticmethod
    def _add_or_tag(
        results: dict[tuple[EmbeddableEntityType, UUID], SearchResult],
        entity_type: EmbeddableEntityType,
        entity_id: UUID,
        name: str,
        description: str | None,
        score: float,
        via: str,
    ) -> None:
        key = (entity_type, entity_id)
        if key in results:
            SearchService._tag_only(results, entity_type, entity_id, via)
            return
        results[key] = SearchResult(
            entity_type=entity_type,
            entity_id=entity_id,
            name=name,
            description=description,
            score=score,
            matched_via=[via],
        )

    @staticmethod
    def _tag_only(
        results: dict[tuple[EmbeddableEntityType, UUID], SearchResult],
        entity_type: EmbeddableEntityType,
        entity_id: UUID,
        via: str,
    ) -> None:
        existing = results[(entity_type, entity_id)]
        if via not in existing.matched_via:
            existing.matched_via.append(via)
