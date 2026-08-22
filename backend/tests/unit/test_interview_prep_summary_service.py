"""Unit tests for InterviewPrepSummaryService — fake repositories, no
database. Mirrors the fake-repository pattern established in
tests/unit/test_interview_topic_service.py /
tests/unit/test_target_role_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.career_profile.target_role_service import TargetRoleService
from app.application.interview_prep.interview_prep_summary_service import (
    InterviewPrepSummaryService,
)
from app.domain.career_profile.entities import TargetRole
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic

pytestmark = pytest.mark.unit


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

    async def move(self, tenant_id: uuid.UUID, topic_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError("not exercised by these tests")


class FakeInterviewQuestionRepository:
    def __init__(self) -> None:
        self.questions: dict[uuid.UUID, InterviewQuestion] = {}

    async def create(self, question: InterviewQuestion) -> InterviewQuestion:
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
        return [
            q
            for q in self.questions.values()
            if q.tenant_id == tenant_id
            and q.user_id == user_id
            and target_role_id in q.scope_target_role_ids
        ]

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        self.questions[question.id] = question
        return question

    async def soft_delete(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> None:
        self.questions.pop(question_id, None)

    async def move(self, tenant_id: uuid.UUID, question_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError("not exercised by these tests")


class FakeTargetRoleRepository:
    """Mirrors tests/unit/test_target_role_service.py's fake of the
    same name — duplicated here (not imported) since these are two
    independent test modules, matching this suite's existing convention
    of a fresh fake per test file rather than a shared test-only
    fixtures module."""

    def __init__(self) -> None:
        self.target_roles: dict[uuid.UUID, TargetRole] = {}

    async def create(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def get_by_id(
        self, tenant_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> TargetRole | None:
        target_role = self.target_roles.get(target_role_id)
        return target_role if target_role and target_role.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[TargetRole]:
        return [
            r
            for r in self.target_roles.values()
            if r.tenant_id == tenant_id and r.user_id == user_id
        ]

    async def update(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def soft_delete(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> None:
        self.target_roles.pop(target_role_id, None)


def make_topic(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
) -> InterviewTopic:
    now = datetime.now(UTC)
    return InterviewTopic(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        name="Some topic",
        scope_target_role_ids=[target_role_id],
        created_at=now,
        updated_at=now,
    )


def make_question(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
) -> InterviewQuestion:
    now = datetime.now(UTC)
    return InterviewQuestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        question="Some question",
        scope_target_role_ids=[target_role_id],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def service() -> tuple[
    InterviewPrepSummaryService,
    FakeInterviewTopicRepository,
    FakeInterviewQuestionRepository,
    TargetRoleService,
]:
    topics = FakeInterviewTopicRepository()
    questions = FakeInterviewQuestionRepository()
    target_roles = TargetRoleService(FakeTargetRoleRepository())
    return InterviewPrepSummaryService(topics, questions, target_roles), topics, questions, target_roles


class TestGetSummary:
    async def test_empty_scopes_are_excluded(
        self,
        service: tuple[
            InterviewPrepSummaryService,
            FakeInterviewTopicRepository,
            FakeInterviewQuestionRepository,
            TargetRoleService,
        ],
    ) -> None:
        summary_service, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        summary = await summary_service.get_summary(tenant_id=tenant_id, user_id=user_id)

        assert summary.scopes == []
        assert summary.total_topic_count == 0
        assert summary.total_question_count == 0

    async def test_master_scope_included_once_it_has_an_artifact(
        self,
        service: tuple[
            InterviewPrepSummaryService,
            FakeInterviewTopicRepository,
            FakeInterviewQuestionRepository,
            TargetRoleService,
        ],
    ) -> None:
        summary_service, topics, questions, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        await topics.create(make_topic(tenant_id=tenant_id, user_id=user_id, target_role_id=None))
        await topics.create(make_topic(tenant_id=tenant_id, user_id=user_id, target_role_id=None))
        await questions.create(
            make_question(tenant_id=tenant_id, user_id=user_id, target_role_id=None)
        )

        summary = await summary_service.get_summary(tenant_id=tenant_id, user_id=user_id)

        assert len(summary.scopes) == 1
        assert summary.scopes[0].target_role_id is None
        assert summary.scopes[0].role_name == "Master"
        assert summary.scopes[0].topic_count == 2
        assert summary.scopes[0].question_count == 1
        assert summary.total_topic_count == 2
        assert summary.total_question_count == 1

    async def test_target_role_scope_included_only_with_an_artifact(
        self,
        service: tuple[
            InterviewPrepSummaryService,
            FakeInterviewTopicRepository,
            FakeInterviewQuestionRepository,
            TargetRoleService,
        ],
    ) -> None:
        summary_service, _, questions, target_roles = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        role_with_content = await target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )
        role_without_content = await target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Manager", tag="MGR"
        )
        await questions.create(
            make_question(
                tenant_id=tenant_id, user_id=user_id, target_role_id=role_with_content.id
            )
        )

        summary = await summary_service.get_summary(tenant_id=tenant_id, user_id=user_id)

        role_names = {s.role_name for s in summary.scopes}
        assert "Staff Engineer" in role_names
        assert role_without_content.role_name not in role_names

    async def test_scopes_are_isolated_by_user(
        self,
        service: tuple[
            InterviewPrepSummaryService,
            FakeInterviewTopicRepository,
            FakeInterviewQuestionRepository,
            TargetRoleService,
        ],
    ) -> None:
        summary_service, topics, _, _ = service
        tenant_id = uuid.uuid4()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()

        await topics.create(make_topic(tenant_id=tenant_id, user_id=user_a, target_role_id=None))

        summary_for_b = await summary_service.get_summary(tenant_id=tenant_id, user_id=user_b)

        assert summary_for_b.scopes == []
        assert summary_for_b.total_topic_count == 0

    async def test_total_counts_dedupe_a_topic_tagged_into_multiple_scopes(
        self,
        service: tuple[
            InterviewPrepSummaryService,
            FakeInterviewTopicRepository,
            FakeInterviewQuestionRepository,
            TargetRoleService,
        ],
    ) -> None:
        summary_service, topics, _, target_roles = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role = await target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )
        # One topic tagged into BOTH Master and the role — appears in
        # both scopes' own lists (topic_count=1 each), but must only
        # count once toward the true total.
        now = datetime.now(UTC)
        multi_scope_topic = InterviewTopic(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name="Multi-scope topic",
            scope_target_role_ids=[None, role.id],
            created_at=now,
            updated_at=now,
        )
        await topics.create(multi_scope_topic)

        summary = await summary_service.get_summary(tenant_id=tenant_id, user_id=user_id)

        assert len(summary.scopes) == 2
        assert all(s.topic_count == 1 for s in summary.scopes)
        assert summary.total_topic_count == 1
