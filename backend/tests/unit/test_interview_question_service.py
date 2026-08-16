"""Unit tests for InterviewQuestionService — fake repositories, no
database. Mirrors the fake-repository pattern established in
tests/unit/test_target_role_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.interview_prep.interview_question_service import InterviewQuestionService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic, ReferenceLink

pytestmark = pytest.mark.unit


class FakeInterviewQuestionRepository:
    def __init__(self) -> None:
        self.questions: dict[uuid.UUID, InterviewQuestion] = {}
        self._order_counter = 0

    async def create(self, question: InterviewQuestion) -> InterviewQuestion:
        self._order_counter += 1
        question.display_order = self._order_counter
        self.questions[question.id] = question
        return question

    async def get_by_id(
        self, tenant_id: uuid.UUID, question_id: uuid.UUID
    ) -> InterviewQuestion | None:
        question = self.questions.get(question_id)
        return question if question and question.tenant_id == tenant_id else None

    async def list_for_scope(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> list[InterviewQuestion]:
        return sorted(
            (
                q
                for q in self.questions.values()
                if q.tenant_id == tenant_id
                and q.user_id == user_id
                and q.target_role_id == target_role_id
            ),
            key=lambda q: q.display_order,
        )

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        self.questions[question.id] = question
        return question

    async def soft_delete(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> None:
        self.questions.pop(question_id, None)

    async def move(self, tenant_id: uuid.UUID, question_id: uuid.UUID, direction: str) -> None:
        q = self.questions[question_id]
        items = await self.list_for_scope(tenant_id, q.user_id, q.target_role_id)
        index = next(i for i, item in enumerate(items) if item.id == question_id)
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(items):
            return
        items[index].display_order, items[neighbor_index].display_order = (
            items[neighbor_index].display_order,
            items[index].display_order,
        )


class FakeInterviewTopicRepository:
    def __init__(self) -> None:
        self.topics: dict[uuid.UUID, InterviewTopic] = {}

    async def create(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        return topic

    async def get_by_id(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> InterviewTopic | None:
        topic = self.topics.get(topic_id)
        return topic if topic and topic.tenant_id == tenant_id else None

    async def list_for_scope(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> list[InterviewTopic]:
        return [
            t
            for t in self.topics.values()
            if t.tenant_id == tenant_id and t.user_id == user_id and t.target_role_id == target_role_id
        ]

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        return topic

    async def soft_delete(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        self.topics.pop(topic_id, None)

    async def move(self, tenant_id: uuid.UUID, topic_id: uuid.UUID, direction: str) -> None:
        pass


def _make_topic(tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs: object) -> InterviewTopic:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        target_role_id=None,
        name="System Design",
        display_order=0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return InterviewTopic(**defaults)  # type: ignore[arg-type]


class TestAdd:
    async def test_adds_a_question(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            topic_id=None,
            question="Tell me about a time you disagreed with a teammate.",
        )

        assert question.question.startswith("Tell me about a time")
        assert questions_repo.questions[question.id] is question

    async def test_rejects_blank_question(self) -> None:
        service = InterviewQuestionService(
            FakeInterviewQuestionRepository(), FakeInterviewTopicRepository()
        )
        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                target_role_id=None,
                topic_id=None,
                question="   ",
            )

    async def test_rejects_a_topic_from_a_different_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role_id = uuid.uuid4()
        topics_repo = FakeInterviewTopicRepository()
        # Topic belongs to Master (target_role_id=None), question is for a specific role.
        topic = await topics_repo.create(_make_topic(tenant_id, user_id, target_role_id=None))
        service = InterviewQuestionService(FakeInterviewQuestionRepository(), topics_repo)

        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role_id,
                topic_id=topic.id,
                question="Some question?",
            )

    async def test_accepts_a_topic_from_the_same_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        topics_repo = FakeInterviewTopicRepository()
        topic = await topics_repo.create(_make_topic(tenant_id, user_id, target_role_id=None))
        service = InterviewQuestionService(FakeInterviewQuestionRepository(), topics_repo)

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            topic_id=topic.id,
            question="Some question?",
        )

        assert question.topic_id == topic.id


class TestUpdate:
    async def test_manual_answer_is_sanitized_on_save(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="Original?",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="Original?",
            manual_answer='<b>Bold</b> <script>alert(1)</script><img src=x onerror=alert(1)>',
            reference_links=[],
        )

        assert updated.manual_answer == "<b>Bold</b> alert(1)"

    async def test_update_requires_ownership(self) -> None:
        tenant_id, user_id, other_user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="Original?",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(NotFoundError):
            await service.update(
                tenant_id=tenant_id,
                user_id=other_user,
                question_id=question.id,
                topic_id=None,
                question="Changed?",
                manual_answer=None,
                reference_links=[],
            )

    async def test_editing_the_question_text_clears_the_ai_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="Original?",
                ai_answer="A stale AI answer.",
                ai_answer_status="generated",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="A totally different question?",
            manual_answer=None,
            reference_links=[],
        )

        assert updated.ai_answer is None
        assert updated.ai_answer_status is None

    async def test_editing_without_changing_question_text_keeps_the_ai_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="Original?",
                ai_answer="A good AI answer.",
                ai_answer_status="generated",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="Original?",
            manual_answer="My own answer.",
            reference_links=[ReferenceLink(url="https://example.com", label="Reference")],
        )

        assert updated.ai_answer == "A good AI answer."
        assert updated.manual_answer == "My own answer."
        assert updated.reference_links == [ReferenceLink(url="https://example.com", label="Reference")]


class TestMove:
    async def test_move_swaps_display_order_within_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        first = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="First?",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        second = await questions_repo.create(
            InterviewQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=None,
                question="Second?",
                display_order=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.move(
            tenant_id=tenant_id, user_id=user_id, question_id=second.id, direction="up"
        )

        ordered = await questions_repo.list_for_scope(tenant_id, user_id, None)
        assert [q.id for q in ordered] == [second.id, first.id]
