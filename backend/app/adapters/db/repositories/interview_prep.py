"""SQLAlchemy repository implementations for the Interview Preparation
domain. Mirrors the mapping-function pattern established in
app/adapters/db/repositories/learning_intelligence.py for the base
create/get/update/soft_delete shape — the scoping half is genuinely
different, since InterviewTopic/InterviewQuestion are now tagged into
zero-or-more scopes via InterviewTopicScopeTagModel/
InterviewQuestionScopeTagModel rather than owning a single exclusive
target_role_id column. See app/domain/interview_prep/entities.py's
module docstring for the full "why".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    InterviewQuestionModel,
    InterviewQuestionScopeTagModel,
    InterviewTopicModel,
    InterviewTopicScopeTagModel,
)
from app.adapters.db.reorder import Direction, move_item, next_display_order
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic, ReferenceLink


def _links_to_domain(raw: list[dict[str, str]]) -> list[ReferenceLink]:
    return [ReferenceLink(url=item["url"], label=item["label"]) for item in raw]


def _links_to_json(links: list[ReferenceLink]) -> list[dict[str, str]]:
    return [{"url": link.url, "label": link.label} for link in links]


def _scope_condition(model_cls: type[Any], target_role_id: UUID | None) -> Any:
    """`target_role_id IS NULL` needs `.is_(None)`, not `== None` —
    shared by every scope-tag query in this module (topics and
    questions alike). `type[Any]`/`Any` here mirror
    app/adapters/db/reorder.py's own documented `type[Any]` trade-off
    for the same SQLAlchemy declarative-class-typing friction."""
    return (
        model_cls.target_role_id == target_role_id
        if target_role_id is not None
        else model_cls.target_role_id.is_(None)
    )


def _topic_to_domain(model: InterviewTopicModel, scope_target_role_ids: list[UUID | None]) -> InterviewTopic:
    return InterviewTopic(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        name=model.name,
        section=model.section,
        discussion=model.discussion,
        image_key=model.image_key,
        reference_links=_links_to_domain(model.reference_links),
        scope_target_role_ids=scope_target_role_ids,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyInterviewTopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _tags_for(self, topic_id: UUID) -> list[UUID | None]:
        result = await self._session.execute(
            select(InterviewTopicScopeTagModel.target_role_id).where(
                InterviewTopicScopeTagModel.topic_id == topic_id
            )
        )
        return list(result.scalars().all())

    async def _tags_for_many(self, topic_ids: list[UUID]) -> dict[UUID, list[UUID | None]]:
        if not topic_ids:
            return {}
        result = await self._session.execute(
            select(InterviewTopicScopeTagModel.topic_id, InterviewTopicScopeTagModel.target_role_id).where(
                InterviewTopicScopeTagModel.topic_id.in_(topic_ids)
            )
        )
        by_topic: dict[UUID, list[UUID | None]] = {tid: [] for tid in topic_ids}
        for topic_id, target_role_id in result.all():
            by_topic[topic_id].append(target_role_id)
        return by_topic

    async def create(self, topic: InterviewTopic) -> InterviewTopic:
        model = InterviewTopicModel(
            id=topic.id,
            tenant_id=topic.tenant_id,
            user_id=topic.user_id,
            name=topic.name,
            section=topic.section,
            discussion=topic.discussion,
            image_key=topic.image_key,
            reference_links=_links_to_json(topic.reference_links),
        )
        self._session.add(model)
        await self._session.flush()

        for target_role_id in topic.scope_target_role_ids:
            order = await next_display_order(
                self._session,
                InterviewTopicScopeTagModel,
                tenant_id=topic.tenant_id,
                scope_filter=(InterviewTopicScopeTagModel.user_id == topic.user_id)
                & _scope_condition(InterviewTopicScopeTagModel, target_role_id),
            )
            self._session.add(
                InterviewTopicScopeTagModel(
                    tenant_id=topic.tenant_id,
                    user_id=topic.user_id,
                    topic_id=topic.id,
                    target_role_id=target_role_id,
                    display_order=order,
                )
            )
        await self._session.flush()
        await self._session.refresh(model)
        return _topic_to_domain(model, list(topic.scope_target_role_ids))

    async def get_by_id(self, tenant_id: UUID, topic_id: UUID) -> InterviewTopic | None:
        result = await self._session.execute(
            select(InterviewTopicModel).where(
                InterviewTopicModel.tenant_id == tenant_id,
                InterviewTopicModel.id == topic_id,
                InterviewTopicModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _topic_to_domain(model, await self._tags_for(topic_id))

    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewTopic]:
        result = await self._session.execute(
            select(InterviewTopicModel)
            .join(InterviewTopicScopeTagModel, InterviewTopicScopeTagModel.topic_id == InterviewTopicModel.id)
            .where(
                InterviewTopicModel.tenant_id == tenant_id,
                InterviewTopicModel.deleted_at.is_(None),
                InterviewTopicScopeTagModel.user_id == user_id,
                _scope_condition(InterviewTopicScopeTagModel, target_role_id),
            )
            .order_by(InterviewTopicScopeTagModel.display_order.asc())
        )
        models = list(result.scalars().all())
        tags_by_topic = await self._tags_for_many([m.id for m in models])
        return [_topic_to_domain(m, tags_by_topic[m.id]) for m in models]

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        model = await self._session.get(InterviewTopicModel, topic.id)
        assert model is not None, "update() called with a topic id that no longer exists"
        model.name = topic.name
        model.section = topic.section
        model.discussion = topic.discussion
        model.image_key = topic.image_key
        model.reference_links = _links_to_json(topic.reference_links)

        current = await self._session.execute(
            select(InterviewTopicScopeTagModel).where(InterviewTopicScopeTagModel.topic_id == topic.id)
        )
        current_tags = list(current.scalars().all())
        current_role_ids = {t.target_role_id for t in current_tags}
        desired_role_ids = set(topic.scope_target_role_ids)

        for tag in current_tags:
            if tag.target_role_id not in desired_role_ids:
                await self._session.delete(tag)

        for target_role_id in desired_role_ids - current_role_ids:
            order = await next_display_order(
                self._session,
                InterviewTopicScopeTagModel,
                tenant_id=topic.tenant_id,
                scope_filter=(InterviewTopicScopeTagModel.user_id == topic.user_id)
                & _scope_condition(InterviewTopicScopeTagModel, target_role_id),
            )
            self._session.add(
                InterviewTopicScopeTagModel(
                    tenant_id=topic.tenant_id,
                    user_id=topic.user_id,
                    topic_id=topic.id,
                    target_role_id=target_role_id,
                    display_order=order,
                )
            )

        await self._session.flush()
        await self._session.refresh(model)
        return _topic_to_domain(model, list(topic.scope_target_role_ids))

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

    async def remove_scope(
        self, tenant_id: UUID, topic_id: UUID, target_role_id: UUID | None
    ) -> None:
        result = await self._session.execute(
            select(InterviewTopicScopeTagModel).where(
                InterviewTopicScopeTagModel.tenant_id == tenant_id,
                InterviewTopicScopeTagModel.topic_id == topic_id,
                _scope_condition(InterviewTopicScopeTagModel, target_role_id),
            )
        )
        tag = result.scalar_one_or_none()
        if tag is not None:
            await self._session.delete(tag)
            await self._session.flush()

    async def move(
        self, tenant_id: UUID, topic_id: UUID, target_role_id: UUID | None, direction: Direction
    ) -> None:
        model = await self._session.get(InterviewTopicModel, topic_id)
        if model is None or model.deleted_at is not None:
            return
        result = await self._session.execute(
            select(InterviewTopicScopeTagModel)
            .join(InterviewTopicModel, InterviewTopicScopeTagModel.topic_id == InterviewTopicModel.id)
            .where(
                InterviewTopicScopeTagModel.tenant_id == tenant_id,
                InterviewTopicScopeTagModel.user_id == model.user_id,
                _scope_condition(InterviewTopicScopeTagModel, target_role_id),
                InterviewTopicModel.deleted_at.is_(None),
            )
            .order_by(InterviewTopicScopeTagModel.display_order.asc())
        )
        tags = list(result.scalars().all())
        index = next((i for i, t in enumerate(tags) if t.topic_id == topic_id), None)
        if index is None:
            return
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(tags):
            return
        current_tag, neighbor_tag = tags[index], tags[neighbor_index]
        current_tag.display_order, neighbor_tag.display_order = (
            neighbor_tag.display_order,
            current_tag.display_order,
        )
        await self._session.flush()


def _question_to_domain(
    model: InterviewQuestionModel,
    scope_target_role_ids: list[UUID | None],
    follow_ups: list[InterviewQuestion] | None = None,
) -> InterviewQuestion:
    return InterviewQuestion(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        topic_id=model.topic_id,
        question=model.question,
        category=model.category,
        manual_answer=model.manual_answer,
        ai_answer=model.ai_answer,
        ai_answer_status=model.ai_answer_status,
        ai_answer_error=model.ai_answer_error,
        ai_answer_generated_at=model.ai_answer_generated_at,
        reference_links=_links_to_domain(model.reference_links),
        scope_target_role_ids=scope_target_role_ids,
        parent_question_id=model.parent_question_id,
        follow_ups=follow_ups or [],
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyInterviewQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _tags_for(self, question_id: UUID) -> list[UUID | None]:
        result = await self._session.execute(
            select(InterviewQuestionScopeTagModel.target_role_id).where(
                InterviewQuestionScopeTagModel.question_id == question_id
            )
        )
        return list(result.scalars().all())

    async def _tags_for_many(self, question_ids: list[UUID]) -> dict[UUID, list[UUID | None]]:
        if not question_ids:
            return {}
        result = await self._session.execute(
            select(
                InterviewQuestionScopeTagModel.question_id, InterviewQuestionScopeTagModel.target_role_id
            ).where(InterviewQuestionScopeTagModel.question_id.in_(question_ids))
        )
        by_question: dict[UUID, list[UUID | None]] = {qid: [] for qid in question_ids}
        for question_id, target_role_id in result.all():
            by_question[question_id].append(target_role_id)
        return by_question

    async def create(self, question: InterviewQuestion) -> InterviewQuestion:
        display_order = 0
        if question.parent_question_id is not None:
            # A follow-up isn't scope-tagged (see this repository's own
            # module docstring) — its position is a flat per-row column,
            # scoped among siblings sharing the same parent, computed the
            # same way every scope-tag row's own display_order already is.
            display_order = await next_display_order(
                self._session,
                InterviewQuestionModel,
                tenant_id=question.tenant_id,
                scope_filter=InterviewQuestionModel.parent_question_id
                == question.parent_question_id,
            )
        model = InterviewQuestionModel(
            id=question.id,
            tenant_id=question.tenant_id,
            user_id=question.user_id,
            topic_id=question.topic_id,
            parent_question_id=question.parent_question_id,
            display_order=display_order,
            question=question.question,
            category=question.category,
            manual_answer=question.manual_answer,
            ai_answer=question.ai_answer,
            ai_answer_status=question.ai_answer_status,
            ai_answer_error=question.ai_answer_error,
            ai_answer_generated_at=question.ai_answer_generated_at,
            reference_links=_links_to_json(question.reference_links),
        )
        self._session.add(model)
        await self._session.flush()

        for target_role_id in question.scope_target_role_ids:
            order = await next_display_order(
                self._session,
                InterviewQuestionScopeTagModel,
                tenant_id=question.tenant_id,
                scope_filter=(InterviewQuestionScopeTagModel.user_id == question.user_id)
                & _scope_condition(InterviewQuestionScopeTagModel, target_role_id),
            )
            self._session.add(
                InterviewQuestionScopeTagModel(
                    tenant_id=question.tenant_id,
                    user_id=question.user_id,
                    question_id=question.id,
                    target_role_id=target_role_id,
                    display_order=order,
                )
            )
        await self._session.flush()
        await self._session.refresh(model)
        return _question_to_domain(model, list(question.scope_target_role_ids))

    async def get_by_id(self, tenant_id: UUID, question_id: UUID) -> InterviewQuestion | None:
        result = await self._session.execute(
            select(InterviewQuestionModel).where(
                InterviewQuestionModel.tenant_id == tenant_id,
                InterviewQuestionModel.id == question_id,
                InterviewQuestionModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _question_to_domain(model, await self._tags_for(question_id))

    async def _follow_ups_for_many(
        self, parent_ids: list[UUID]
    ) -> dict[UUID, list[InterviewQuestion]]:
        """Batched, not one query per parent — follow-ups have no scope
        tags of their own (see this repository's own module docstring),
        so this is a plain query on parent_question_id, not the
        scope-tag join list_for_scope()/get_by_id() use for top-level
        questions."""
        by_parent: dict[UUID, list[InterviewQuestion]] = {pid: [] for pid in parent_ids}
        if not parent_ids:
            return by_parent
        result = await self._session.execute(
            select(InterviewQuestionModel)
            .where(
                InterviewQuestionModel.parent_question_id.in_(parent_ids),
                InterviewQuestionModel.deleted_at.is_(None),
            )
            .order_by(InterviewQuestionModel.display_order.asc())
        )
        for model in result.scalars().all():
            assert model.parent_question_id is not None
            by_parent[model.parent_question_id].append(_question_to_domain(model, []))
        return by_parent

    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewQuestion]:
        result = await self._session.execute(
            select(InterviewQuestionModel)
            .join(
                InterviewQuestionScopeTagModel,
                InterviewQuestionScopeTagModel.question_id == InterviewQuestionModel.id,
            )
            .where(
                InterviewQuestionModel.tenant_id == tenant_id,
                InterviewQuestionModel.deleted_at.is_(None),
                InterviewQuestionScopeTagModel.user_id == user_id,
                _scope_condition(InterviewQuestionScopeTagModel, target_role_id),
            )
            .order_by(InterviewQuestionScopeTagModel.display_order.asc())
        )
        # The join above naturally excludes follow-ups (they have no
        # scope-tag rows of their own) — this list is top-level
        # questions only, each with its own follow_ups nested in.
        models = list(result.scalars().all())
        tags_by_question = await self._tags_for_many([m.id for m in models])
        follow_ups_by_parent = await self._follow_ups_for_many([m.id for m in models])
        return [
            _question_to_domain(m, tags_by_question[m.id], follow_ups_by_parent[m.id])
            for m in models
        ]

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        model = await self._session.get(InterviewQuestionModel, question.id)
        assert model is not None, "update() called with a question id that no longer exists"
        model.topic_id = question.topic_id
        model.question = question.question
        model.category = question.category
        model.manual_answer = question.manual_answer
        model.ai_answer = question.ai_answer
        model.ai_answer_status = question.ai_answer_status
        model.ai_answer_error = question.ai_answer_error
        model.ai_answer_generated_at = question.ai_answer_generated_at
        model.reference_links = _links_to_json(question.reference_links)

        current = await self._session.execute(
            select(InterviewQuestionScopeTagModel).where(
                InterviewQuestionScopeTagModel.question_id == question.id
            )
        )
        current_tags = list(current.scalars().all())
        current_role_ids = {t.target_role_id for t in current_tags}
        desired_role_ids = set(question.scope_target_role_ids)

        for tag in current_tags:
            if tag.target_role_id not in desired_role_ids:
                await self._session.delete(tag)

        for target_role_id in desired_role_ids - current_role_ids:
            order = await next_display_order(
                self._session,
                InterviewQuestionScopeTagModel,
                tenant_id=question.tenant_id,
                scope_filter=(InterviewQuestionScopeTagModel.user_id == question.user_id)
                & _scope_condition(InterviewQuestionScopeTagModel, target_role_id),
            )
            self._session.add(
                InterviewQuestionScopeTagModel(
                    tenant_id=question.tenant_id,
                    user_id=question.user_id,
                    question_id=question.id,
                    target_role_id=target_role_id,
                    display_order=order,
                )
            )

        await self._session.flush()
        await self._session.refresh(model)
        # A top-level question already has follow-ups by the time it's
        # being edited — omitting them here would make the returned
        # object (which callers write straight into the frontend cache)
        # silently drop them until the next full list refetch. A
        # follow-up itself never has follow_ups of its own (single level
        # only), so this is a no-op query for that case.
        follow_ups: list[InterviewQuestion] = []
        if model.parent_question_id is None:
            follow_ups = (await self._follow_ups_for_many([model.id]))[model.id]
        return _question_to_domain(model, list(question.scope_target_role_ids), follow_ups)

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

    async def remove_scope(
        self, tenant_id: UUID, question_id: UUID, target_role_id: UUID | None
    ) -> None:
        result = await self._session.execute(
            select(InterviewQuestionScopeTagModel).where(
                InterviewQuestionScopeTagModel.tenant_id == tenant_id,
                InterviewQuestionScopeTagModel.question_id == question_id,
                _scope_condition(InterviewQuestionScopeTagModel, target_role_id),
            )
        )
        tag = result.scalar_one_or_none()
        if tag is not None:
            await self._session.delete(tag)
            await self._session.flush()

    async def move(
        self, tenant_id: UUID, question_id: UUID, target_role_id: UUID | None, direction: Direction
    ) -> None:
        model = await self._session.get(InterviewQuestionModel, question_id)
        if model is None or model.deleted_at is not None:
            return
        result = await self._session.execute(
            select(InterviewQuestionScopeTagModel)
            .join(
                InterviewQuestionModel,
                InterviewQuestionScopeTagModel.question_id == InterviewQuestionModel.id,
            )
            .where(
                InterviewQuestionScopeTagModel.tenant_id == tenant_id,
                InterviewQuestionScopeTagModel.user_id == model.user_id,
                _scope_condition(InterviewQuestionScopeTagModel, target_role_id),
                InterviewQuestionModel.deleted_at.is_(None),
            )
            .order_by(InterviewQuestionScopeTagModel.display_order.asc())
        )
        tags = list(result.scalars().all())
        index = next((i for i, t in enumerate(tags) if t.question_id == question_id), None)
        if index is None:
            return
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(tags):
            return
        current_tag, neighbor_tag = tags[index], tags[neighbor_index]
        current_tag.display_order, neighbor_tag.display_order = (
            neighbor_tag.display_order,
            current_tag.display_order,
        )
        await self._session.flush()

    async def list_follow_ups(
        self, tenant_id: UUID, parent_question_id: UUID
    ) -> list[InterviewQuestion]:
        return (await self._follow_ups_for_many([parent_question_id]))[parent_question_id]

    async def move_follow_up(
        self, tenant_id: UUID, follow_up_id: UUID, direction: Direction
    ) -> None:
        model = await self._session.get(InterviewQuestionModel, follow_up_id)
        if model is None or model.deleted_at is not None or model.parent_question_id is None:
            return
        # A follow-up's ordering is a plain column on the row itself,
        # scoped among siblings sharing the same parent — reuses the
        # same centralized swap logic every other orderable entity in
        # this app delegates to, unlike top-level questions' own
        # bespoke, scope-tag-table-based move() above.
        await move_item(
            self._session,
            InterviewQuestionModel,
            tenant_id=tenant_id,
            scope_filter=InterviewQuestionModel.parent_question_id == model.parent_question_id,
            item_id=follow_up_id,
            direction=direction,
        )
