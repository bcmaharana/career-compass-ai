"""Interview Question application service.

Questions are scoped by user_id plus a many-to-many set of tagged
scopes (scope_target_role_ids — None means Master, a real id means a
specific Target Role; see app/domain/interview_prep/entities.py's
module docstring for the full multi-scope-tagging design). `topic_id`
is the one link this service does verify before accepting: it must
belong to the same user — the previous "and the same scope" half of
that check no longer makes sense once both questions and topics can
each be tagged into multiple, possibly non-identical, scopes.
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


def _dedupe_scopes(scope_target_role_ids: list[UUID | None]) -> list[UUID | None]:
    """Preserves order while dropping duplicates — a plain `list(set(...))`
    would both lose order and choke on `None` sorting inconsistently."""
    return list(dict.fromkeys(scope_target_role_ids))


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
        self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID | None
    ) -> None:
        if topic_id is None:
            return
        topic = await self._topics.get_by_id(tenant_id, topic_id)
        if topic is None or topic.user_id != user_id:
            raise ValidationError("That topic doesn't belong to you.", code="INVALID_TOPIC_LINK")

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID | None,
        question: str,
        category: str | None = None,
        scope_target_role_ids: list[UUID | None],
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")
        deduped = _dedupe_scopes(scope_target_role_ids)
        if not deduped:
            raise ValidationError(
                "A question must be tagged to at least one scope.", code="SCOPE_REQUIRED"
            )
        await self._validate_topic_link(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)

        now = datetime.now(UTC)
        return await self._questions.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic_id,
                question=trimmed,
                category=category,
                scope_target_role_ids=deduped,
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
        category: str | None,
        manual_answer: str | None,
        reference_links: list[ReferenceLink],
        scope_target_role_ids: list[UUID | None],
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")
        deduped = _dedupe_scopes(scope_target_role_ids)
        if not deduped:
            raise ValidationError(
                "A question must be tagged to at least one scope.", code="SCOPE_REQUIRED"
            )

        existing = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, question_id=question_id
        )
        await self._validate_topic_link(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)

        existing.topic_id = topic_id
        existing.category = category
        existing.manual_answer = sanitize_rich_text(manual_answer)
        existing.reference_links = reference_links
        existing.scope_target_role_ids = deduped
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

    async def delete(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        question_id: UUID,
        target_role_id: UUID | None,
        delete_everywhere: bool,
    ) -> None:
        """Deletes the question entirely if `delete_everywhere` is true,
        or if it's only tagged to `target_role_id` in the first place
        (see InterviewTopicService.delete's identical reasoning — a
        single-scope item has no meaningful "just this scope" option).
        Otherwise, untags it from just `target_role_id`, leaving it
        intact under its other tagged scopes."""
        question = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, question_id=question_id
        )
        if delete_everywhere or len(question.scope_target_role_ids) <= 1:
            await self._questions.soft_delete(tenant_id, question_id)
        else:
            await self._questions.remove_scope(tenant_id, question_id, target_role_id)

    async def move(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        question_id: UUID,
        target_role_id: UUID | None,
        direction: Direction,
    ) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, question_id=question_id)
        await self._questions.move(tenant_id, question_id, target_role_id, direction)

    # --- Follow-up questions ---
    #
    # The same InterviewQuestion shape, linked via parent_question_id —
    # see app/domain/interview_prep/entities.py's docstring for the full
    # "why". Single level only: add_follow_up rejects a parent that is
    # itself already a follow-up. Never scope-tagged, never given a
    # topic_id/category of their own — no equivalent of add()'s
    # scope/topic/category params here.

    async def get_owned_follow_up_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, follow_up_id: UUID
    ) -> InterviewQuestion:
        follow_up = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, question_id=follow_up_id
        )
        if follow_up.parent_question_id is None:
            raise NotFoundError(
                "Interview question not found.", code="INTERVIEW_QUESTION_NOT_FOUND"
            )
        return follow_up

    async def add_follow_up(
        self, *, tenant_id: UUID, user_id: UUID, parent_question_id: UUID, question: str
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")

        parent = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, question_id=parent_question_id
        )
        if parent.parent_question_id is not None:
            raise ValidationError(
                "A follow-up question can't have follow-ups of its own.",
                code="FOLLOW_UP_NESTING_NOT_ALLOWED",
            )

        now = datetime.now(UTC)
        return await self._questions.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                question=trimmed,
                parent_question_id=parent_question_id,
                scope_target_role_ids=[],
                created_at=now,
                updated_at=now,
            )
        )

    async def update_follow_up(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        follow_up_id: UUID,
        question: str,
        manual_answer: str | None,
        reference_links: list[ReferenceLink],
    ) -> InterviewQuestion:
        trimmed = question.strip()
        if not trimmed:
            raise ValidationError("Question is required.", code="INTERVIEW_QUESTION_REQUIRED")

        existing = await self.get_owned_follow_up_or_raise(
            tenant_id=tenant_id, user_id=user_id, follow_up_id=follow_up_id
        )
        existing.manual_answer = sanitize_rich_text(manual_answer)
        existing.reference_links = reference_links
        if existing.question != trimmed:
            existing.ai_answer = None
            existing.ai_answer_status = None
            existing.ai_answer_error = None
            existing.ai_answer_generated_at = None
        existing.question = trimmed
        return await self._questions.update(existing)

    async def delete_follow_up(
        self, *, tenant_id: UUID, user_id: UUID, follow_up_id: UUID
    ) -> None:
        await self.get_owned_follow_up_or_raise(
            tenant_id=tenant_id, user_id=user_id, follow_up_id=follow_up_id
        )
        await self._questions.soft_delete(tenant_id, follow_up_id)

    async def move_follow_up(
        self, *, tenant_id: UUID, user_id: UUID, follow_up_id: UUID, direction: Direction
    ) -> list[InterviewQuestion]:
        follow_up = await self.get_owned_follow_up_or_raise(
            tenant_id=tenant_id, user_id=user_id, follow_up_id=follow_up_id
        )
        await self._questions.move_follow_up(tenant_id, follow_up_id, direction)
        assert follow_up.parent_question_id is not None
        return await self._questions.list_follow_ups(tenant_id, follow_up.parent_question_id)
