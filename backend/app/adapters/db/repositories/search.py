"""SQLAlchemy repositories for CIKG search infrastructure (Phase 4.5.1
MVP 2A) — see app/adapters/db/models/search.py's module docstring.

`SqlAlchemySearchRepository` holds the raw hybrid-search SQL (cosine
KNN via pgvector, `ts_rank` full-text, graph-filter joins) that doesn't
fit the plain-dataclass repository Protocol shape the rest of this
package uses — the same "direct parameterized SQL for a
Postgres-specific concern the ORM doesn't model well" precedent as
`app/adapters/db/base.py`'s `set_tenant_context`. `entity_type` is
always the `EmbeddableEntityType` Literal (validated at the Pydantic
schema boundary before it ever reaches here), never an arbitrary
caller-supplied string — table names below are selected from a fixed
internal mapping, never interpolated from user input directly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    CikgRoleModel,
    CompetencyModel,
    ContentEmbeddingModel,
    EmbeddingModelModel,
    RelatedSkillModel,
    RoleRequiredSkillModel,
    SkillCategoryMembershipModel,
    SkillCompetencyMembershipModel,
    SkillModel,
)
from app.domain.career_intelligence.entities import (
    ContentEmbedding,
    EmbeddableEntityType,
    EmbeddingModel,
)

_TABLE_BY_ENTITY_TYPE = {
    "skill": "skills",
    "cikg_role": "cikg_roles",
    "competency": "competencies",
}
_NAME_COLUMN_BY_ENTITY_TYPE = {
    "skill": "name",
    "cikg_role": "title",
    "competency": "name",
}


def _embedding_model_to_domain(model: EmbeddingModelModel) -> EmbeddingModel:
    return EmbeddingModel(
        id=model.id,
        provider=model.provider,
        model_name=model.model_name,
        dimensions=model.dimensions,
        is_default=model.is_default,
        created_at=model.created_at,
    )


def _content_embedding_to_domain(model: ContentEmbeddingModel) -> ContentEmbedding:
    return ContentEmbedding(
        id=model.id,
        entity_type=model.entity_type,  # type: ignore[arg-type]
        entity_id=model.entity_id,
        embedding_model_id=model.embedding_model_id,
        embedding=list(model.embedding),
        source_text_hash=model.source_text_hash,
        generated_at=model.generated_at,
    )


class SqlAlchemyEmbeddingModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, model: EmbeddingModel) -> EmbeddingModel:
        row = EmbeddingModelModel(
            id=model.id,
            provider=model.provider,
            model_name=model.model_name,
            dimensions=model.dimensions,
            is_default=model.is_default,
        )
        self._session.add(row)
        await self._session.flush()
        return _embedding_model_to_domain(row)

    async def get_by_model_name(self, model_name: str) -> EmbeddingModel | None:
        result = await self._session.execute(
            select(EmbeddingModelModel).where(EmbeddingModelModel.model_name == model_name)
        )
        row = result.scalar_one_or_none()
        return _embedding_model_to_domain(row) if row else None

    async def get_default(self) -> EmbeddingModel | None:
        result = await self._session.execute(
            select(EmbeddingModelModel).where(EmbeddingModelModel.is_default.is_(True))
        )
        row = result.scalar_one_or_none()
        return _embedding_model_to_domain(row) if row else None


class SqlAlchemyContentEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, embedding: ContentEmbedding) -> ContentEmbedding:
        existing = await self.get_by_entity(
            embedding.entity_type, embedding.entity_id, embedding.embedding_model_id
        )
        if existing is not None:
            row = await self._session.get(ContentEmbeddingModel, existing.id)
            assert row is not None
            row.embedding = embedding.embedding
            row.source_text_hash = embedding.source_text_hash
            await self._session.flush()
            await self._session.refresh(row)
            return _content_embedding_to_domain(row)

        row = ContentEmbeddingModel(
            id=embedding.id,
            entity_type=embedding.entity_type,
            entity_id=embedding.entity_id,
            embedding_model_id=embedding.embedding_model_id,
            embedding=embedding.embedding,
            source_text_hash=embedding.source_text_hash,
        )
        self._session.add(row)
        await self._session.flush()
        return _content_embedding_to_domain(row)

    async def get_by_entity(
        self, entity_type: EmbeddableEntityType, entity_id: UUID, embedding_model_id: UUID
    ) -> ContentEmbedding | None:
        result = await self._session.execute(
            select(ContentEmbeddingModel).where(
                ContentEmbeddingModel.entity_type == entity_type,
                ContentEmbeddingModel.entity_id == entity_id,
                ContentEmbeddingModel.embedding_model_id == embedding_model_id,
            )
        )
        row = result.scalar_one_or_none()
        return _content_embedding_to_domain(row) if row else None

    async def list_hashes_for_type(
        self, entity_type: EmbeddableEntityType, embedding_model_id: UUID
    ) -> dict[UUID, str]:
        result = await self._session.execute(
            select(ContentEmbeddingModel.entity_id, ContentEmbeddingModel.source_text_hash).where(
                ContentEmbeddingModel.entity_type == entity_type,
                ContentEmbeddingModel.embedding_model_id == embedding_model_id,
            )
        )
        return {entity_id: text_hash for entity_id, text_hash in result.all()}


class SqlAlchemySearchRepository:
    """Raw hybrid-search SQL. Every method takes `entity_type` as the
    `EmbeddableEntityType` Literal, mapping it through the fixed
    `_TABLE_BY_ENTITY_TYPE`/`_NAME_COLUMN_BY_ENTITY_TYPE` dicts above —
    never interpolating a caller-supplied string as a table/column name.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fulltext_search(
        self, entity_type: EmbeddableEntityType, query: str, *, limit: int
    ) -> list[tuple[UUID, str, str | None, float]]:
        """Returns (entity_id, name, description, rank), ranked by
        ts_rank, restricted to approved content only."""
        table = _TABLE_BY_ENTITY_TYPE[entity_type]
        name_column = _NAME_COLUMN_BY_ENTITY_TYPE[entity_type]
        result = await self._session.execute(
            sql_text(
                f"""
                SELECT id, {name_column} AS name, description,
                       ts_rank(search_vector, plainto_tsquery('english', :query)) AS rank
                FROM {table}
                WHERE content_status = 'approved'
                  AND deleted_at IS NULL
                  AND search_vector @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :limit
                """
            ),
            {"query": query, "limit": limit},
        )
        return [(row.id, row.name, row.description, float(row.rank)) for row in result.all()]

    async def vector_search(
        self,
        entity_type: EmbeddableEntityType,
        query_embedding: list[float],
        embedding_model_id: UUID,
        *,
        limit: int,
    ) -> list[tuple[UUID, float]]:
        """Returns (entity_id, similarity) via pgvector cosine distance
        (`<=>`), similarity = 1 - distance so higher is more similar,
        matching ts_rank's "higher is better" direction."""
        result = await self._session.execute(
            sql_text(
                """
                SELECT entity_id, 1 - (embedding <=> :query_embedding) AS similarity
                FROM content_embeddings
                WHERE entity_type = :entity_type AND embedding_model_id = :embedding_model_id
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
                """
            ),
            {
                "query_embedding": str(query_embedding),
                "entity_type": entity_type,
                "embedding_model_id": embedding_model_id,
                "limit": limit,
            },
        )
        return [(row.entity_id, float(row.similarity)) for row in result.all()]

    async def get_names(
        self, entity_type: EmbeddableEntityType, entity_ids: list[UUID]
    ) -> dict[UUID, tuple[str, str | None]]:
        """entity_id -> (name, description) for a specific set of ids —
        used to hydrate vector-only hits that fulltext_search didn't
        already return alongside their name/description."""
        if not entity_ids:
            return {}
        table = _TABLE_BY_ENTITY_TYPE[entity_type]
        name_column = _NAME_COLUMN_BY_ENTITY_TYPE[entity_type]
        result = await self._session.execute(
            sql_text(
                f"""
                SELECT id, {name_column} AS name, description FROM {table}
                WHERE id = ANY(:ids) AND content_status = 'approved' AND deleted_at IS NULL
                """
            ),
            {"ids": entity_ids},
        )
        return {row.id: (row.name, row.description) for row in result.all()}

    async def relationship_count(self, entity_type: EmbeddableEntityType, entity_id: UUID) -> int:
        """Count of approved edges touching this node — the
        "relationship richness" factor of knowledge_quality_score
        (cikg-semantic-search.md)."""
        if entity_type == "skill":
            # Four separate counts, summed in Python — clearer than one
            # contorted UNION query for a rarely-hot path.
            counts = []
            for model, column in (
                (SkillCategoryMembershipModel, SkillCategoryMembershipModel.skill_id),
                (SkillCompetencyMembershipModel, SkillCompetencyMembershipModel.skill_id),
                (RoleRequiredSkillModel, RoleRequiredSkillModel.skill_id),
            ):
                r = await self._session.execute(
                    select(model.id).where(column == entity_id, model.content_status == "approved")
                )
                counts.append(len(r.all()))
            r = await self._session.execute(
                select(RelatedSkillModel.id).where(
                    (
                        (RelatedSkillModel.skill_a_id == entity_id)
                        | (RelatedSkillModel.skill_b_id == entity_id)
                    ),
                    RelatedSkillModel.content_status == "approved",
                )
            )
            counts.append(len(r.all()))
            return sum(counts)

        if entity_type == "cikg_role":
            r = await self._session.execute(
                select(RoleRequiredSkillModel.id).where(
                    RoleRequiredSkillModel.role_id == entity_id,
                    RoleRequiredSkillModel.content_status == "approved",
                )
            )
            return len(r.all())

        # competency
        r = await self._session.execute(
            select(SkillCompetencyMembershipModel.id).where(
                SkillCompetencyMembershipModel.competency_id == entity_id,
                SkillCompetencyMembershipModel.content_status == "approved",
            )
        )
        return len(r.all())

    async def filter_skill_ids_by_category(self, category_id: UUID) -> set[UUID]:
        result = await self._session.execute(
            select(SkillCategoryMembershipModel.skill_id).where(
                SkillCategoryMembershipModel.category_id == category_id,
                SkillCategoryMembershipModel.content_status == "approved",
            )
        )
        return set(result.scalars().all())

    async def filter_skill_ids_by_role(self, role_id: UUID) -> set[UUID]:
        result = await self._session.execute(
            select(RoleRequiredSkillModel.skill_id).where(
                RoleRequiredSkillModel.role_id == role_id,
                RoleRequiredSkillModel.content_status == "approved",
            )
        )
        return set(result.scalars().all())
