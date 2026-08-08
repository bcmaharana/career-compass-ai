"""Embedding generation/indexing for CIKG search (Phase 4.5.1 MVP 2A).

`EmbeddingIndexingService.reindex_all()` is the one entry point —
called by `scripts/embed_cikg_content.py`. Idempotent: compares each
node's current embeddable text against the hash already stored for it
(`ContentEmbedding.source_text_hash`) and only calls the embedding
provider for nodes that are new or changed, per
cikg-semantic-search.md's re-embedding-trigger design.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from app.ai_platform.embeddings.provider_interface import EmbeddingProviderInterface
from app.domain.career_intelligence.entities import (
    CikgRole,
    Competency,
    ContentEmbedding,
    EmbeddableEntityType,
    EmbeddingModel,
    Skill,
)
from app.domain.career_intelligence.repositories import (
    CikgRoleRepository,
    CompetencyRepository,
    ContentEmbeddingRepository,
    EmbeddingModelRepository,
    SkillRepository,
)


def _embeddable_text(name: str, description: str | None) -> str:
    return f"{name}. {description}" if description else name


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingIndexingService:
    def __init__(
        self,
        embedding_provider: EmbeddingProviderInterface,
        embedding_models: EmbeddingModelRepository,
        content_embeddings: ContentEmbeddingRepository,
        skills: SkillRepository,
        roles: CikgRoleRepository,
        competencies: CompetencyRepository,
        *,
        model_name: str,
        provider_name: str,
        dimensions: int,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_models = embedding_models
        self._content_embeddings = content_embeddings
        self._skills = skills
        self._roles = roles
        self._competencies = competencies
        self._model_name = model_name
        self._provider_name = provider_name
        self._dimensions = dimensions

    async def _get_or_create_embedding_model(self) -> EmbeddingModel:
        existing = await self._embedding_models.get_by_model_name(self._model_name)
        if existing is not None:
            return existing
        return await self._embedding_models.create(
            EmbeddingModel(
                id=uuid.uuid4(),
                provider=self._provider_name,
                model_name=self._model_name,
                dimensions=self._dimensions,
                is_default=True,
                created_at=datetime.now(UTC),
            )
        )

    async def reindex_all(self) -> dict[EmbeddableEntityType, int]:
        """Re-embed every approved Skill/CikgRole/Competency whose
        embeddable text is new or has changed since its last embed.
        Returns the count actually re-embedded per entity type (not the
        total node count — nodes already up to date aren't touched).
        """
        embedding_model = await self._get_or_create_embedding_model()

        skill_count = await self._reindex_skills(embedding_model.id)
        role_count = await self._reindex_roles(embedding_model.id)
        competency_count = await self._reindex_competencies(embedding_model.id)

        return {"skill": skill_count, "cikg_role": role_count, "competency": competency_count}

    async def _reindex_skills(self, embedding_model_id: uuid.UUID) -> int:
        skills: list[Skill] = await self._skills.list_approved()
        existing_hashes = await self._content_embeddings.list_hashes_for_type(
            "skill", embedding_model_id
        )
        return await self._reindex_nodes(
            entity_type="skill",
            nodes=[(s.id, _embeddable_text(s.name, s.description)) for s in skills],
            existing_hashes=existing_hashes,
            embedding_model_id=embedding_model_id,
        )

    async def _reindex_roles(self, embedding_model_id: uuid.UUID) -> int:
        roles: list[CikgRole] = await self._roles.list_approved()
        existing_hashes = await self._content_embeddings.list_hashes_for_type(
            "cikg_role", embedding_model_id
        )
        return await self._reindex_nodes(
            entity_type="cikg_role",
            nodes=[(r.id, _embeddable_text(r.title, r.description)) for r in roles],
            existing_hashes=existing_hashes,
            embedding_model_id=embedding_model_id,
        )

    async def _reindex_competencies(self, embedding_model_id: uuid.UUID) -> int:
        competencies: list[Competency] = await self._competencies.list_approved()
        existing_hashes = await self._content_embeddings.list_hashes_for_type(
            "competency", embedding_model_id
        )
        return await self._reindex_nodes(
            entity_type="competency",
            nodes=[(c.id, _embeddable_text(c.name, c.description)) for c in competencies],
            existing_hashes=existing_hashes,
            embedding_model_id=embedding_model_id,
        )

    async def _reindex_nodes(
        self,
        *,
        entity_type: EmbeddableEntityType,
        nodes: list[tuple[uuid.UUID, str]],
        existing_hashes: dict[uuid.UUID, str],
        embedding_model_id: uuid.UUID,
    ) -> int:
        stale = [
            (entity_id, text)
            for entity_id, text in nodes
            if existing_hashes.get(entity_id) != _hash_text(text)
        ]
        if not stale:
            return 0

        vectors = await self._embedding_provider.embed(
            texts=[text for _, text in stale], model_name=self._model_name
        )
        for (entity_id, text), vector in zip(stale, vectors, strict=True):
            await self._content_embeddings.upsert(
                ContentEmbedding(
                    id=uuid.uuid4(),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    embedding_model_id=embedding_model_id,
                    embedding=vector,
                    source_text_hash=_hash_text(text),
                    generated_at=datetime.now(UTC),
                )
            )
        return len(stale)
