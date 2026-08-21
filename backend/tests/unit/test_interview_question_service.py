"""Unit tests for InterviewQuestionService — fake repositories, no
database. Mirrors the fake-repository pattern established in
tests/unit/test_target_role_service.py and
tests/unit/test_interview_topic_service.py (same
dict[item_id, dict[target_role_id, display_order]] simulation of the
real many-to-many scope-tag join table).
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
        self.tags: dict[uuid.UUID, dict[uuid.UUID | None, int]] = {}
        self._order_counters: dict[tuple[uuid.UUID, uuid.UUID | None], int] = {}
        # Follow-ups aren't scope-tagged (see this repository's real
        # counterpart) — a separate order tracked per parent, mirroring
        # SqlAlchemyInterviewQuestionRepository's plain display_order
        # column rather than the tag-table simulation above.
        self._follow_up_order: dict[uuid.UUID, int] = {}
        self._follow_up_order_counters: dict[uuid.UUID, int] = {}

    def _next_order(self, user_id: uuid.UUID, target_role_id: uuid.UUID | None) -> int:
        key = (user_id, target_role_id)
        self._order_counters[key] = self._order_counters.get(key, 0) + 1
        return self._order_counters[key]

    def _next_follow_up_order(self, parent_id: uuid.UUID) -> int:
        self._follow_up_order_counters[parent_id] = (
            self._follow_up_order_counters.get(parent_id, 0) + 1
        )
        return self._follow_up_order_counters[parent_id]

    async def create(self, question: InterviewQuestion) -> InterviewQuestion:
        self.questions[question.id] = question
        self.tags[question.id] = {
            rid: self._next_order(question.user_id, rid) for rid in question.scope_target_role_ids
        }
        if question.parent_question_id is not None:
            self._follow_up_order[question.id] = self._next_follow_up_order(
                question.parent_question_id
            )
        return question

    async def get_by_id(
        self, tenant_id: uuid.UUID, question_id: uuid.UUID
    ) -> InterviewQuestion | None:
        question = self.questions.get(question_id)
        if question is None or question.tenant_id != tenant_id:
            return None
        question.scope_target_role_ids = list(self.tags.get(question_id, {}).keys())
        return question

    async def list_for_scope(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> list[InterviewQuestion]:
        matches: list[tuple[int, InterviewQuestion]] = []
        for question_id, tag_map in self.tags.items():
            if target_role_id not in tag_map:
                continue
            question = self.questions.get(question_id)
            if question is None or question.tenant_id != tenant_id or question.user_id != user_id:
                continue
            matches.append((tag_map[target_role_id], question))
        matches.sort(key=lambda pair: pair[0])
        for _, question in matches:
            question.scope_target_role_ids = list(self.tags[question.id].keys())
            question.follow_ups = await self.list_follow_ups(tenant_id, question.id)
        return [question for _, question in matches]

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        self.questions[question.id] = question
        current = self.tags.setdefault(question.id, {})
        desired = set(question.scope_target_role_ids)
        for rid in list(current.keys()):
            if rid not in desired:
                del current[rid]
        for rid in desired - set(current.keys()):
            current[rid] = self._next_order(question.user_id, rid)
        if question.parent_question_id is None:
            question.follow_ups = await self.list_follow_ups(question.tenant_id, question.id)
        return question

    async def soft_delete(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> None:
        self.questions.pop(question_id, None)
        self.tags.pop(question_id, None)
        self._follow_up_order.pop(question_id, None)

    async def remove_scope(
        self, tenant_id: uuid.UUID, question_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> None:
        if question_id in self.tags:
            self.tags[question_id].pop(target_role_id, None)

    async def move(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
        target_role_id: uuid.UUID | None,
        direction: str,
    ) -> None:
        items = await self.list_for_scope(tenant_id, self.questions[question_id].user_id, target_role_id)
        index = next((i for i, item in enumerate(items) if item.id == question_id), None)
        if index is None:
            return
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(items):
            return
        neighbor_id = items[neighbor_index].id
        self.tags[question_id][target_role_id], self.tags[neighbor_id][target_role_id] = (
            self.tags[neighbor_id][target_role_id],
            self.tags[question_id][target_role_id],
        )

    async def list_follow_ups(
        self, tenant_id: uuid.UUID, parent_question_id: uuid.UUID
    ) -> list[InterviewQuestion]:
        matches = [
            (self._follow_up_order.get(q.id, 0), q)
            for q in self.questions.values()
            if q.parent_question_id == parent_question_id and q.tenant_id == tenant_id
        ]
        matches.sort(key=lambda pair: pair[0])
        return [q for _, q in matches]

    async def move_follow_up(
        self, tenant_id: uuid.UUID, follow_up_id: uuid.UUID, direction: str
    ) -> None:
        question = self.questions.get(follow_up_id)
        if question is None or question.parent_question_id is None:
            return
        siblings = await self.list_follow_ups(tenant_id, question.parent_question_id)
        index = next((i for i, s in enumerate(siblings) if s.id == follow_up_id), None)
        if index is None:
            return
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(siblings):
            return
        neighbor_id = siblings[neighbor_index].id
        self._follow_up_order[follow_up_id], self._follow_up_order[neighbor_id] = (
            self._follow_up_order[neighbor_id],
            self._follow_up_order[follow_up_id],
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
            if t.tenant_id == tenant_id
            and t.user_id == user_id
            and target_role_id in t.scope_target_role_ids
        ]

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        return topic

    async def soft_delete(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        self.topics.pop(topic_id, None)

    async def remove_scope(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> None:
        topic = self.topics.get(topic_id)
        if topic is not None and target_role_id in topic.scope_target_role_ids:
            topic.scope_target_role_ids.remove(target_role_id)

    async def move(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None, direction: str
    ) -> None:
        pass


def _make_topic(tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs: object) -> InterviewTopic:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        name="System Design",
        scope_target_role_ids=[None],
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return InterviewTopic(**defaults)  # type: ignore[arg-type]


def _make_question(tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs: object) -> InterviewQuestion:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        question="Original?",
        scope_target_role_ids=[None],
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return InterviewQuestion(**defaults)  # type: ignore[arg-type]


class TestAdd:
    async def test_adds_a_question(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=None,
            question="Tell me about a time you disagreed with a teammate.",
            scope_target_role_ids=[None],
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
                topic_id=None,
                question="   ",
                scope_target_role_ids=[None],
            )

    async def test_rejects_an_empty_scope_list(self) -> None:
        service = InterviewQuestionService(
            FakeInterviewQuestionRepository(), FakeInterviewTopicRepository()
        )
        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                topic_id=None,
                question="Some question?",
                scope_target_role_ids=[],
            )

    async def test_rejects_a_topic_owned_by_a_different_user(self) -> None:
        tenant_id, user_id, other_user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        topics_repo = FakeInterviewTopicRepository()
        topic = await topics_repo.create(_make_topic(tenant_id, other_user))
        service = InterviewQuestionService(FakeInterviewQuestionRepository(), topics_repo)

        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                question="Some question?",
                scope_target_role_ids=[None],
            )

    async def test_accepts_a_topic_owned_by_the_same_user_regardless_of_its_own_scopes(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        topics_repo = FakeInterviewTopicRepository()
        # Topic tagged only to a specific role; question tagged to Master —
        # no longer required to match, only ownership matters now.
        topic = await topics_repo.create(_make_topic(tenant_id, user_id, scope_target_role_ids=[role_id]))
        service = InterviewQuestionService(FakeInterviewQuestionRepository(), topics_repo)

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            question="Some question?",
            scope_target_role_ids=[None],
        )

        assert question.topic_id == topic.id

    async def test_adds_a_question_with_a_category(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewQuestionService(
            FakeInterviewQuestionRepository(), FakeInterviewTopicRepository()
        )

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=None,
            question="Describe a conflict you resolved.",
            category="Behavioral",
            scope_target_role_ids=[None],
        )

        assert question.category == "Behavioral"

    async def test_category_defaults_to_none(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewQuestionService(
            FakeInterviewQuestionRepository(), FakeInterviewTopicRepository()
        )

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=None,
            question="Uncategorized question?",
            scope_target_role_ids=[None],
        )

        assert question.category is None

    async def test_tags_into_multiple_scopes(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewQuestionRepository()
        service = InterviewQuestionService(repo, FakeInterviewTopicRepository())

        question = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=None,
            question="Cross-tagged question?",
            scope_target_role_ids=[None, role_id],
        )

        assert set(question.scope_target_role_ids) == {None, role_id}
        master_list = await repo.list_for_scope(tenant_id, user_id, None)
        role_list = await repo.list_for_scope(tenant_id, user_id, role_id)
        assert [q.id for q in master_list] == [question.id]
        assert [q.id for q in role_list] == [question.id]


class TestUpdate:
    async def test_manual_answer_is_sanitized_on_save(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="Original?",
            category=None,
            manual_answer='<b>Bold</b> <script>alert(1)</script><img src=x onerror=alert(1)>',
            reference_links=[],
            scope_target_role_ids=[None],
        )

        assert updated.manual_answer == "<b>Bold</b> alert(1)"

    async def test_update_requires_ownership(self) -> None:
        tenant_id, user_id, other_user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(NotFoundError):
            await service.update(
                tenant_id=tenant_id,
                user_id=other_user,
                question_id=question.id,
                topic_id=None,
                question="Changed?",
                category=None,
                manual_answer=None,
                reference_links=[],
                scope_target_role_ids=[None],
            )

    async def test_update_rejects_an_empty_scope_list(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                question_id=question.id,
                topic_id=None,
                question="Original?",
                category=None,
                manual_answer=None,
                reference_links=[],
                scope_target_role_ids=[],
            )

    async def test_editing_the_question_text_clears_the_ai_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(
                tenant_id, user_id, ai_answer="A stale AI answer.", ai_answer_status="generated"
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="A totally different question?",
            category=None,
            manual_answer=None,
            reference_links=[],
            scope_target_role_ids=[None],
        )

        assert updated.ai_answer is None
        assert updated.ai_answer_status is None

    async def test_editing_without_changing_question_text_keeps_the_ai_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(
                tenant_id, user_id, ai_answer="A good AI answer.", ai_answer_status="generated"
            )
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="Original?",
            category=None,
            manual_answer="My own answer.",
            reference_links=[ReferenceLink(url="https://example.com", label="Reference")],
            scope_target_role_ids=[None],
        )

        assert updated.ai_answer == "A good AI answer."
        assert updated.manual_answer == "My own answer."
        assert updated.reference_links == [ReferenceLink(url="https://example.com", label="Reference")]

    async def test_update_can_add_a_scope_tag(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))  # Master only
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            topic_id=None,
            question="Original?",
            category=None,
            manual_answer=None,
            reference_links=[],
            scope_target_role_ids=[None, role_id],
        )

        assert set(updated.scope_target_role_ids) == {None, role_id}

    async def test_update_rejects_a_javascript_scheme_reference_link(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                question_id=question.id,
                topic_id=None,
                question="Original?",
                category=None,
                manual_answer=None,
                reference_links=[
                    ReferenceLink(url="javascript:alert(document.cookie)", label="Evil")
                ],
                scope_target_role_ids=[None],
            )


class TestDelete:
    async def test_delete_removes_everywhere_when_only_one_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert question.id not in questions_repo.questions

    async def test_delete_from_just_this_scope_leaves_the_question_visible_elsewhere(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(tenant_id, user_id, scope_target_role_ids=[None, role_id])
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert question.id in questions_repo.questions
        master_list = await questions_repo.list_for_scope(tenant_id, user_id, None)
        role_list = await questions_repo.list_for_scope(tenant_id, user_id, role_id)
        assert master_list == []
        assert [q.id for q in role_list] == [question.id]

    async def test_delete_everywhere_removes_it_from_every_tagged_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(tenant_id, user_id, scope_target_role_ids=[None, role_id])
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=question.id,
            target_role_id=None,
            delete_everywhere=True,
        )

        assert question.id not in questions_repo.questions


class TestMove:
    async def test_move_swaps_display_order_within_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        first = await questions_repo.create(_make_question(tenant_id, user_id, question="First?"))
        second = await questions_repo.create(_make_question(tenant_id, user_id, question="Second?"))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.move(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=second.id,
            target_role_id=None,
            direction="up",
        )

        ordered = await questions_repo.list_for_scope(tenant_id, user_id, None)
        assert [q.id for q in ordered] == [second.id, first.id]

    async def test_move_is_independent_per_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        first = await questions_repo.create(
            _make_question(tenant_id, user_id, question="First?", scope_target_role_ids=[None, role_id])
        )
        second = await questions_repo.create(
            _make_question(tenant_id, user_id, question="Second?", scope_target_role_ids=[None, role_id])
        )
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        await service.move(
            tenant_id=tenant_id,
            user_id=user_id,
            question_id=second.id,
            target_role_id=role_id,
            direction="up",
        )

        role_ordered = await questions_repo.list_for_scope(tenant_id, user_id, role_id)
        master_ordered = await questions_repo.list_for_scope(tenant_id, user_id, None)
        assert [q.id for q in role_ordered] == [second.id, first.id]
        assert [q.id for q in master_ordered] == [first.id, second.id]


class TestFollowUps:
    async def test_add_follow_up_links_to_parent_with_no_scope_tags(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        follow_up = await service.add_follow_up(
            tenant_id=tenant_id,
            user_id=user_id,
            parent_question_id=parent.id,
            question="And how did that turn out?",
        )

        assert follow_up.parent_question_id == parent.id
        assert follow_up.scope_target_role_ids == []
        assert follow_up.topic_id is None
        assert follow_up.category is None

    async def test_add_follow_up_rejects_blank_question(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(ValidationError):
            await service.add_follow_up(
                tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="   "
            )

    async def test_add_follow_up_rejects_a_parent_owned_by_a_different_user(self) -> None:
        tenant_id = uuid.uuid4()
        owner_id, other_user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, owner_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(NotFoundError):
            await service.add_follow_up(
                tenant_id=tenant_id,
                user_id=other_user_id,
                parent_question_id=parent.id,
                question="Follow-up?",
            )

    async def test_add_follow_up_rejects_nesting_under_another_follow_up(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )

        with pytest.raises(ValidationError, match="follow-ups of its own"):
            await service.add_follow_up(
                tenant_id=tenant_id,
                user_id=user_id,
                parent_question_id=follow_up.id,
                question="Nested follow-up?",
            )

    async def test_list_for_scope_nests_follow_ups_under_their_parent(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )

        top_level = await service.list_for_scope(tenant_id=tenant_id, user_id=user_id, target_role_id=None)

        assert len(top_level) == 1
        assert [f.id for f in top_level[0].follow_ups] == [follow_up.id]

    async def test_update_follow_up_saves_answer_and_links_without_scope_validation(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )

        updated = await service.update_follow_up(
            tenant_id=tenant_id,
            user_id=user_id,
            follow_up_id=follow_up.id,
            question="Follow-up?",
            manual_answer="<p>My answer.</p>",
            reference_links=[ReferenceLink(url="https://example.com", label="Ref")],
        )

        assert updated.manual_answer == "<p>My answer.</p>"
        assert updated.reference_links == [ReferenceLink(url="https://example.com", label="Ref")]

    async def test_update_follow_up_clears_stale_ai_answer_on_text_change(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )
        follow_up.ai_answer = "Stale answer."
        follow_up.ai_answer_status = "generated"

        updated = await service.update_follow_up(
            tenant_id=tenant_id,
            user_id=user_id,
            follow_up_id=follow_up.id,
            question="Different follow-up?",
            manual_answer=None,
            reference_links=[],
        )

        assert updated.ai_answer is None
        assert updated.ai_answer_status is None

    async def test_update_follow_up_rejects_a_data_scheme_reference_link(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )

        with pytest.raises(ValidationError):
            await service.update_follow_up(
                tenant_id=tenant_id,
                user_id=user_id,
                follow_up_id=follow_up.id,
                question="Follow-up?",
                manual_answer=None,
                reference_links=[
                    ReferenceLink(url="data:text/html,<script>alert(1)</script>", label="Evil")
                ],
            )

    async def test_update_follow_up_rejects_a_top_level_question_id(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        top_level = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())

        with pytest.raises(NotFoundError):
            await service.update_follow_up(
                tenant_id=tenant_id,
                user_id=user_id,
                follow_up_id=top_level.id,
                question="Not actually a follow-up",
                manual_answer=None,
                reference_links=[],
            )

    async def test_delete_follow_up_removes_only_the_follow_up(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        follow_up = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Follow-up?"
        )

        await service.delete_follow_up(tenant_id=tenant_id, user_id=user_id, follow_up_id=follow_up.id)

        assert follow_up.id not in questions_repo.questions
        assert parent.id in questions_repo.questions

    async def test_move_follow_up_reorders_among_siblings_only(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(_make_question(tenant_id, user_id))
        service = InterviewQuestionService(questions_repo, FakeInterviewTopicRepository())
        first = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="First follow-up?"
        )
        second = await service.add_follow_up(
            tenant_id=tenant_id, user_id=user_id, parent_question_id=parent.id, question="Second follow-up?"
        )

        siblings = await service.move_follow_up(
            tenant_id=tenant_id, user_id=user_id, follow_up_id=second.id, direction="up"
        )

        assert [f.id for f in siblings] == [second.id, first.id]
