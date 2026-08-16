"""Interview Question application service.

Questions are scoped directly by user_id, optionally tied to a Target
Role (same trust-the-caller-supplied-id precedent LearningItemService
already established for its own target_role_id — no extra ownership
round-trip there). `topic_id` is the one link this service does verify
before accepting: it must belong to the same user *and* the same scope
(target_role_id) as the question itself, since a Master-scoped question
linking to a target-role-specific topic (or vice versa) would be a
genuinely confusing state, not just an unusual one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.interview_prep.entities import InterviewQuestion, ReferenceLink
from app.domain.interview_prep.repositories import (
    Direction,
    InterviewQuestionRepository,
    InterviewTopicRepository,
)


class InterviewQuestionService:
    def __init__(
        self, questions: InterviewQuestionRepository, topics: InterviewTopicRepository
    ) -> None:
        self._questions = questions
        self._topics = topics

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, question_id: UUID
    ) -> InterviewQuestion:
        question = await self._questions.get_by_id(tenant_id, question_id)
        if question is None or question.user_id != user_id:
            raise NotFoundError(
                "Interview question not found.", code="INTERVIEW_QUESTION_NOT_FOUND"
            )
        return question

    async def _validate_topic_link(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None, topic_id: UUID | None
    ) -> None:
        if topic_id is None:
            return
        topic = await self._topics.get_by_id(tenant_id, topic_id)
        if topic is None or topic.user_id != user_id or topic.target_role_id != target_role_id:
            raise ValidationError(
                "That topic doesn't belong to this scope.", code="INVALID_TOPIC_LINK"
            )

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        topic_id: UUID | None,
        question: str,
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")
        await self._validate_topic_link(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id, topic_id=topic_id
        )

        now = datetime.now(UTC)
        return await self._questions.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role_id,
                topic_id=topic_id,
                question=trimmed,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_scope(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewQuestion]:
        return await self._questions.list_for_scope(tenant_id, user_id, target_role_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        question_id: UUID,
        topic_id: UUID | None,
        question: str,
        manual_answer: str | None,
        reference_links: list[ReferenceLink],
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")

        existing = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, question_id=question_id
        )
        await self._validate_topic_link(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=existing.target_role_id,
            topic_id=topic_id,
        )

        existing.topic_id = topic_id
        existing.manual_answer = sanitize_rich_text(manual_answer)
        existing.reference_links = reference_links
        # A stale AI answer for a since-edited question would be
        # actively misleading — clear it back to "never generated"
        # rather than leaving old text attached to new wording.
        if existing.question != trimmed:
            existing.ai_answer = None
            existing.ai_answer_status = None
            existing.ai_answer_error = None
            existing.ai_answer_generated_at = None
        existing.question = trimmed
        return await self._questions.update(existing)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, question_id: UUID) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, question_id=question_id)
        await self._questions.soft_delete(tenant_id, question_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, question_id: UUID, direction: Direction
    ) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, question_id=question_id)
        await self._questions.move(tenant_id, question_id, direction)
