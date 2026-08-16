"""SQLAlchemy repository implementations for the Learning Intelligence
domain (Phase 7). Mirrors the mapping-function pattern established in
app/adapters/db/repositories/career_profile.py — LearningItemRepository
in particular mirrors SqlAlchemyCareerGoalRepository almost exactly
(same user_id-scoped, reorderable shape).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import LearningItemModel, LearningRecommendationSetModel
from app.adapters.db.reorder import Direction, move_item, next_display_order
from app.domain.learning_intelligence.entities import LearningItem, LearningRecommendationSet


def _item_to_domain(model: LearningItemModel) -> LearningItem:
    return LearningItem(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        title=model.title,
        provider=model.provider,
        url=model.url,
        status=model.status,
        notes=model.notes,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        target_role_id=model.target_role_id,
        started_at=model.started_at,
        completed_at=model.completed_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyLearningItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, item: LearningItem) -> LearningItem:
        order = await next_display_order(
            self._session,
            LearningItemModel,
            tenant_id=item.tenant_id,
            scope_filter=LearningItemModel.user_id == item.user_id,
        )
        model = LearningItemModel(
            id=item.id,
            tenant_id=item.tenant_id,
            user_id=item.user_id,
            title=item.title,
            provider=item.provider,
            url=item.url,
            status=item.status,
            target_role_id=item.target_role_id,
            notes=item.notes,
            started_at=item.started_at,
            completed_at=item.completed_at,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _item_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, item_id: UUID) -> LearningItem | None:
        result = await self._session.execute(
            select(LearningItemModel).where(
                LearningItemModel.tenant_id == tenant_id,
                LearningItemModel.id == item_id,
                LearningItemModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _item_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[LearningItem]:
        result = await self._session.execute(
            select(LearningItemModel)
            .where(
                LearningItemModel.tenant_id == tenant_id,
                LearningItemModel.user_id == user_id,
                LearningItemModel.deleted_at.is_(None),
            )
            .order_by(LearningItemModel.display_order.asc())
        )
        return [_item_to_domain(model) for model in result.scalars().all()]

    async def update(self, item: LearningItem) -> LearningItem:
        model = await self._session.get(LearningItemModel, item.id)
        assert model is not None, "update() called with an item id that no longer exists"
        model.title = item.title
        model.provider = item.provider
        model.url = item.url
        model.status = item.status
        model.target_role_id = item.target_role_id
        model.notes = item.notes
        model.started_at = item.started_at
        model.completed_at = item.completed_at
        await self._session.flush()
        await self._session.refresh(model)
        return _item_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, item_id: UUID) -> None:
        result = await self._session.execute(
            select(LearningItemModel).where(
                LearningItemModel.tenant_id == tenant_id, LearningItemModel.id == item_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, item_id: UUID, direction: Direction) -> None:
        model = await self._session.get(LearningItemModel, item_id)
        if model is None:
            return
        await move_item(
            self._session,
            LearningItemModel,
            tenant_id=tenant_id,
            scope_filter=LearningItemModel.user_id == model.user_id,
            item_id=item_id,
            direction=direction,
        )


def _recommendation_set_to_domain(
    model: LearningRecommendationSetModel,
) -> LearningRecommendationSet:
    return LearningRecommendationSet(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        target_role_id=model.target_role_id,
        status=model.status,
        missing_skills_hash=model.missing_skills_hash,
        recommendations=list(model.recommendations) if model.recommendations is not None else None,
        error_message=model.error_message,
        generated_at=model.generated_at,
    )


class SqlAlchemyLearningRecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_target_role(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> LearningRecommendationSet | None:
        result = await self._session.execute(
            select(LearningRecommendationSetModel).where(
                LearningRecommendationSetModel.tenant_id == tenant_id,
                LearningRecommendationSetModel.user_id == user_id,
                LearningRecommendationSetModel.target_role_id == target_role_id,
            )
        )
        model = result.scalar_one_or_none()
        return _recommendation_set_to_domain(model) if model else None

    async def upsert(self, rec_set: LearningRecommendationSet) -> LearningRecommendationSet:
        result = await self._session.execute(
            select(LearningRecommendationSetModel).where(
                LearningRecommendationSetModel.tenant_id == rec_set.tenant_id,
                LearningRecommendationSetModel.user_id == rec_set.user_id,
                LearningRecommendationSetModel.target_role_id == rec_set.target_role_id,
            )
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = LearningRecommendationSetModel(
                id=rec_set.id,
                tenant_id=rec_set.tenant_id,
                user_id=rec_set.user_id,
                target_role_id=rec_set.target_role_id,
                status=rec_set.status,
                missing_skills_hash=rec_set.missing_skills_hash,
                recommendations=rec_set.recommendations,
                error_message=rec_set.error_message,
                generated_at=rec_set.generated_at,
            )
            self._session.add(model)
        else:
            model.status = rec_set.status
            model.missing_skills_hash = rec_set.missing_skills_hash
            model.recommendations = rec_set.recommendations
            model.error_message = rec_set.error_message
            model.generated_at = rec_set.generated_at

        await self._session.flush()
        await self._session.refresh(model)
        return _recommendation_set_to_domain(model)
