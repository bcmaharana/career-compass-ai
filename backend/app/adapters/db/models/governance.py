"""SQLAlchemy ORM models for CIKG content governance (Phase 4.5.1
MVP 2B) — the content_revision/content_history mechanics behind
draft→in_review→approved→rejected (cikg-versioning-confidence.md).

Own file — this is cross-cutting workflow infra spanning every CIKG
node/edge type, not one domain's content, same rationale as
app/adapters/db/models/search.py for MVP 2A's embedding infra.

Nothing writes to a live node/edge row except an approved
ContentRevision being applied (see
app/application/career_intelligence/content_revision_service.py) —
these two tables are the entire staging/audit mechanism.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class ContentRevisionModel(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'rejected')", name="status"
        ),
        CheckConstraint(
            "source_attribution IN ('curated', 'ai_suggested', 'bulk_import')",
            name="source_attribution",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    proposed_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    source_attribution: Mapped[str] = mapped_column(String(20), nullable=False)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentHistoryModel(Base):
    __tablename__ = "content_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("content_revisions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
