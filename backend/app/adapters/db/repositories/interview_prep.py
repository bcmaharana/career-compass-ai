"""SQLAlchemy repository implementations for the Interview Preparation
domain. Mirrors the mapping-function pattern established in
app/adapters/db/repositories/learning_intelligence.py —
InterviewTopicRepository/InterviewQuestionRepository both mirror
SqlAlchemyLearningItemRepository almost exactly (same user_id-scoped,
reorderable shape).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import InterviewQuestionModel, InterviewTopicModel
from app.adapters.db.reorder import Direction, move_item, next_display_order
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic, ReferenceLink


def _links_to_domain(raw: list[dict[str, str]]) -> list[ReferenceLink]:
    return [ReferenceLink(url=item["url"], label=item["label"]) for item in raw]


def _links_to_json(links: list[ReferenceLink]) -> list[dict[str, str]]:
    return [{"url": link.url, "label": link.label} for link in links]


def _topic_to_domain(model: InterviewTopicModel) -> InterviewTopic:
    return InterviewTopic(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        target_role_id=model.target_role_id,
        name=model.name,
        section=model.section,
        discussion=model.discussion,
        image_key=model.image_key,
        reference_links=_links_to_domain(model.reference_links),
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyInterviewTopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, topic: InterviewTopic) -> InterviewTopic:
        scope_condition = (
            InterviewTopicModel.target_role_id == topic.target_role_id
            if topic.target_role_id is not None
            else InterviewTopicModel.target_role_id.is_(None)
        )
        order = await next_display_order(
            self._session,
            InterviewTopicModel,
            tenant_id=topic.tenant_id,
            scope_filter=(InterviewTopicModel.user_id == topic.user_id) & scope_condition,
        )
        model = InterviewTopicModel(
            id=topic.id,
            tenant_id=topic.tenant_id,
            user_id=topic.user_id,
            target_role_id=topic.target_role_id,
            name=topic.name,
            section=topic.section,
            discussion=topic.discussion,
            image_key=topic.image_key,
            reference_links=_links_to_json(topic.reference_links),
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _topic_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, topic_id: UUID) -> InterviewTopic | None:
        result = await self._session.execute(
            select(InterviewTopicModel).where(
                InterviewTopicModel.tenant_id == tenant_id,
                InterviewTopicModel.id == topic_id,
                InterviewTopicModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _topic_to_domain(model) if model else None

    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewTopic]:
        scope_condition = (
            InterviewTopicModel.target_role_id == target_role_id
            if target_role_id is not None
            else InterviewTopicModel.target_role_id.is_(None)
        )
        result = await self._session.execute(
            select(InterviewTopicModel)
            .where(
                InterviewTopicModel.tenant_id == tenant_id,
                InterviewTopicModel.user_id == user_id,
                scope_condition,
                InterviewTopicModel.deleted_at.is_(None),
            )
            .order_by(InterviewTopicModel.display_order.asc())
        )
        return [_topic_to_domain(model) for model in result.scalars().all()]

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        model = await self._session.get(InterviewTopicModel, topic.id)
        assert model is not None, "update() called with a topic id that no longer exists"
        model.name = topic.name
        model.section = topic.section
        model.discussion = topic.discussion
        model.image_key = topic.image_key
        model.reference_links = _links_to_json(topic.reference_links)
        await self._session.flush()
        await self._session.refresh(model)
        return _topic_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, topic_id: UUID) -> None:
        result = await self._session.execute(
            select(InterviewTopicModel).where(
                InterviewTopicModel.tenant_id == tenant_id, InterviewTopicModel.id == topic_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, topic_id: UUID, direction: Direction) -> None:
        model = await self._session.get(InterviewTopicModel, topic_id)
        if model is None:
            return
        scope_condition = (
            InterviewTopicModel.target_role_id == model.target_role_id
            if model.target_role_id is not None
            else InterviewTopicModel.target_role_id.is_(None)
        )
        await move_item(
            self._session,
            InterviewTopicModel,
            tenant_id=tenant_id,
            scope_filter=(InterviewTopicModel.user_id == model.user_id) & scope_condition,
            item_id=topic_id,
            direction=direction,
        )


def _question_to_domain(model: InterviewQuestionModel) -> InterviewQuestion:
    return InterviewQuestion(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        target_role_id=model.target_role_id,
        topic_id=model.topic_id,
        question=model.question,
        manual_answer=model.manual_answer,
        ai_answer=model.ai_answer,
        ai_answer_status=model.ai_answer_status,
        ai_answer_error=model.ai_answer_error,
        ai_answer_generated_at=model.ai_answer_generated_at,
        reference_links=_links_to_domain(model.reference_links),
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyInterviewQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, question: InterviewQuestion) -> InterviewQuestion:
        scope_condition = (
            InterviewQuestionModel.target_role_id == question.target_role_id
            if question.target_role_id is not None
            else InterviewQuestionModel.target_role_id.is_(None)
        )
        order = await next_display_order(
            self._session,
            InterviewQuestionModel,
            tenant_id=question.tenant_id,
            scope_filter=(InterviewQuestionModel.user_id == question.user_id) & scope_condition,
        )
        model = InterviewQuestionModel(
            id=question.id,
            tenant_id=question.tenant_id,
            user_id=question.user_id,
            target_role_id=question.target_role_id,
            topic_id=question.topic_id,
            question=question.question,
            manual_answer=question.manual_answer,
            ai_answer=question.ai_answer,
            ai_answer_status=question.ai_answer_status,
            ai_answer_error=question.ai_answer_error,
            ai_answer_generated_at=question.ai_answer_generated_at,
            reference_links=_links_to_json(question.reference_links),
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _question_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, question_id: UUID) -> InterviewQuestion | None:
        result = await self._session.execute(
            select(InterviewQuestionModel).where(
                InterviewQuestionModel.tenant_id == tenant_id,
                InterviewQuestionModel.id == question_id,
                InterviewQuestionModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _question_to_domain(model) if model else None

    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewQuestion]:
        scope_condition = (
            InterviewQuestionModel.target_role_id == target_role_id
            if target_role_id is not None
            else InterviewQuestionModel.target_role_id.is_(None)
        )
        result = await self._session.execute(
            select(InterviewQuestionModel)
            .where(
                InterviewQuestionModel.tenant_id == tenant_id,
                InterviewQuestionModel.user_id == user_id,
                scope_condition,
                InterviewQuestionModel.deleted_at.is_(None),
            )
            .order_by(InterviewQuestionModel.display_order.asc())
        )
        return [_question_to_domain(model) for model in result.scalars().all()]

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        model = await self._session.get(InterviewQuestionModel, question.id)
        assert model is not None, "update() called with a question id that no longer exists"
        model.topic_id = question.topic_id
        model.question = question.question
        model.manual_answer = question.manual_answer
        model.ai_answer = question.ai_answer
        model.ai_answer_status = question.ai_answer_status
        model.ai_answer_error = question.ai_answer_error
        model.ai_answer_generated_at = question.ai_answer_generated_at
        model.reference_links = _links_to_json(question.reference_links)
        await self._session.flush()
        await self._session.refresh(model)
        return _question_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, question_id: UUID) -> None:
        result = await self._session.execute(
            select(InterviewQuestionModel).where(
                InterviewQuestionModel.tenant_id == tenant_id,
                InterviewQuestionModel.id == question_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, question_id: UUID, direction: Direction) -> None:
        model = await self._session.get(InterviewQuestionModel, question_id)
        if model is None:
            return
        scope_condition = (
            InterviewQuestionModel.target_role_id == model.target_role_id
            if model.target_role_id is not None
            else InterviewQuestionModel.target_role_id.is_(None)
        )
        await move_item(
            self._session,
            InterviewQuestionModel,
            tenant_id=tenant_id,
            scope_filter=(InterviewQuestionModel.user_id == model.user_id) & scope_condition,
            item_id=question_id,
            direction=direction,
        )
