"""SQLAlchemy repositories for CIKG content governance (Phase 4.5.1
MVP 2B) — see app/adapters/db/models/governance.py's module docstring.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import ContentHistoryModel, ContentRevisionModel
from app.core.exceptions import NotFoundError
from app.domain.career_intelligence.entities import ContentHistoryEntry, ContentRevision


def _revision_to_domain(model: ContentRevisionModel) -> ContentRevision:
    return ContentRevision(
        id=model.id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        proposed_data=dict(model.proposed_data),
        revision_number=model.revision_number,
        status=model.status,  # type: ignore[arg-type]
        confidence=float(model.confidence) if model.confidence is not None else None,
        source_attribution=model.source_attribution,  # type: ignore[arg-type]
        import_batch_id=model.import_batch_id,
        reviewed_by=model.reviewed_by,
        review_notes=model.review_notes,
        created_at=model.created_at,
        reviewed_at=model.reviewed_at,
    )


def _history_entry_to_domain(model: ContentHistoryModel) -> ContentHistoryEntry:
    return ContentHistoryEntry(
        id=model.id,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        version_number=model.version_number,
        snapshot=dict(model.snapshot),
        change_reason=model.change_reason,
        revision_id=model.revision_id,
        created_at=model.created_at,
    )


class SqlAlchemyContentRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, revision: ContentRevision) -> ContentRevision:
        model = ContentRevisionModel(
            id=revision.id,
            entity_type=revision.entity_type,
            entity_id=revision.entity_id,
            proposed_data=revision.proposed_data,
            revision_number=revision.revision_number,
            status=revision.status,
            confidence=revision.confidence,
            source_attribution=revision.source_attribution,
            import_batch_id=revision.import_batch_id,
            reviewed_by=revision.reviewed_by,
            review_notes=revision.review_notes,
        )
        self._session.add(model)
        await self._session.flush()
        return _revision_to_domain(model)

    async def update(self, revision: ContentRevision) -> ContentRevision:
        """Persists status/review-field transitions, and `entity_id`
        (backfilled by ContentRevisionService.approve() the first time a
        brand-new entity's revision is approved) — never `proposed_data`,
        which is immutable once a revision is created."""
        model = await self._session.get(ContentRevisionModel, revision.id)
        if model is None:
            raise NotFoundError("Content revision not found.", code="CONTENT_REVISION_NOT_FOUND")
        model.entity_id = revision.entity_id
        model.status = revision.status
        model.reviewed_by = revision.reviewed_by
        model.review_notes = revision.review_notes
        model.reviewed_at = revision.reviewed_at
        await self._session.flush()
        await self._session.refresh(model)
        return _revision_to_domain(model)

    async def get_by_id(self, revision_id: UUID) -> ContentRevision | None:
        model = await self._session.get(ContentRevisionModel, revision_id)
        return _revision_to_domain(model) if model else None

    async def list_by_batch(self, import_batch_id: UUID) -> list[ContentRevision]:
        result = await self._session.execute(
            select(ContentRevisionModel).where(
                ContentRevisionModel.import_batch_id == import_batch_id
            )
        )
        return [_revision_to_domain(m) for m in result.scalars().all()]

    async def list_by_status(self, status: str) -> list[ContentRevision]:
        result = await self._session.execute(
            select(ContentRevisionModel).where(ContentRevisionModel.status == status)
        )
        return [_revision_to_domain(m) for m in result.scalars().all()]

    async def count_for_entity(self, entity_type: str, entity_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(
                ContentRevisionModel.entity_type == entity_type,
                ContentRevisionModel.entity_id == entity_id,
            )
        )
        return result.scalar_one()


class SqlAlchemyContentHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: ContentHistoryEntry) -> ContentHistoryEntry:
        model = ContentHistoryModel(
            id=entry.id,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            version_number=entry.version_number,
            snapshot=entry.snapshot,
            change_reason=entry.change_reason,
            revision_id=entry.revision_id,
        )
        self._session.add(model)
        await self._session.flush()
        return _history_entry_to_domain(model)

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> list[ContentHistoryEntry]:
        result = await self._session.execute(
            select(ContentHistoryModel)
            .where(
                ContentHistoryModel.entity_type == entity_type,
                ContentHistoryModel.entity_id == entity_id,
            )
            .order_by(ContentHistoryModel.version_number)
        )
        return [_history_entry_to_domain(m) for m in result.scalars().all()]
