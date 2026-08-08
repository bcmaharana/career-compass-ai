"""SQLAlchemy ORM models for CIKG search infrastructure (Phase 4.5.1
MVP 2A) — cross-cutting retrieval infra, not CIKG-domain content itself
(hence its own file rather than living in career_intelligence.py; per
cikg-ai-agents.md, future domains beyond CIKG will consume this same
retrieval layer for RAG).

`embedding_models` mirrors `model_versions`' shape (ai_platform.py) —
reference data, no tenant_id. `content_embeddings` is the polymorphic
embedding store cikg-semantic-search.md specifies: one row per
(entity_type, entity_id, embedding_model_id) rather than a vector
column bolted onto every embeddable node table, so adding an eleventh
embeddable type later is a content-type string, not a migration.

Requires the `vector` Postgres extension (pgvector) — enabled by this
feature's migration, not a prior one.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base

#: Must match Settings.cikg_embedding_dimensions (nomic-embed-text's
#: output size). Changing embedding models to one with a different
#: dimensionality requires a migration to resize this column, not just
#: a config change — see app/core/config.py's comment.
EMBEDDING_DIMENSIONS = 768


class EmbeddingModelModel(Base):
    __tablename__ = "embedding_models"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentEmbeddingModel(Base):
    __tablename__ = "content_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "embedding_model_id", name="uq_content_embeddings_entity_model"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: 'skill' | 'cikg_role' | 'competency' — no FK, since this is a
    #: polymorphic reference across three different node tables.
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    embedding_model_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("embedding_models.id"), nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    #: sha256 of the exact text that was embedded — lets
    #: EmbeddingIndexingService detect staleness (content changed since
    #: last embed) without re-diffing full text on every check.
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
