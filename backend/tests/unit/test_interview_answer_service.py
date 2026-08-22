"""Unit tests for InterviewAnswerService — fake repositories/LLM, no
database, no real LLM calls. Mirrors the fake-repository pattern
established in tests/unit/test_learning_recommendation_service.py.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.interview_prep.interview_answer_service import InterviewAnswerService
from app.core.exceptions import CareerCompassError
from app.domain.career_profile.entities import (
    CareerProfile,
    CareerProfileVersion,
    CoreCompetency,
    TargetRole,
)
from app.domain.interview_prep.entities import ArticleBlock, ArticleColumn, InterviewQuestion, InterviewTopic

pytestmark = pytest.mark.unit


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
        return list(self.questions.values())

    async def update(self, question: InterviewQuestion) -> InterviewQuestion:
        self.questions[question.id] = question
        return question

    async def soft_delete(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> None:
        self.questions.pop(question_id, None)

    async def remove_scope(
        self, tenant_id: uuid.UUID, question_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> None:
        raise NotImplementedError("not exercised by these tests")

    async def move(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
        target_role_id: uuid.UUID | None,
        direction: str,
    ) -> None:
        pass

    async def list_follow_ups(
        self, tenant_id: uuid.UUID, parent_question_id: uuid.UUID
    ) -> list[InterviewQuestion]:
        return [
            q
            for q in self.questions.values()
            if q.parent_question_id == parent_question_id and q.tenant_id == tenant_id
        ]

    async def move_follow_up(
        self, tenant_id: uuid.UUID, follow_up_id: uuid.UUID, direction: str
    ) -> None:
        raise NotImplementedError("not exercised by these tests")


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
        return list(self.topics.values())

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        return topic

    async def soft_delete(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        self.topics.pop(topic_id, None)

    async def remove_scope(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> None:
        raise NotImplementedError("not exercised by these tests")

    async def move(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None, direction: str
    ) -> None:
        pass


class FakeCareerProfileRepository:
    """Returns copies on fetch, not live references — see
    tests/unit/test_career_profile_service.py's identical fake for why
    this matters."""

    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        target_role_id: uuid.UUID | None = None,
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.user_id == user_id
                and profile.target_role_id == target_role_id
            ):
                return replace(profile)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)


class FakeCareerProfileVersionRepository:
    async def create(self, version: CareerProfileVersion) -> CareerProfileVersion:
        return version

    async def list_for_profile(
        self, career_profile_id: uuid.UUID, *, limit: int = 50
    ) -> list[CareerProfileVersion]:
        return []


class FakeTargetRoleRepository:
    def __init__(self, roles: dict[uuid.UUID, TargetRole]) -> None:
        self.roles = roles

    async def create(self, target_role: TargetRole) -> TargetRole:
        self.roles[target_role.id] = target_role
        return target_role

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        role = self.roles.get(target_role_id)
        return role if role and role.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[TargetRole]:
        return list(self.roles.values())

    async def update(self, target_role: TargetRole) -> TargetRole:
        self.roles[target_role.id] = target_role
        return target_role

    async def soft_delete(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> None:
        self.roles.pop(target_role_id, None)


class FakeLLMService:
    def __init__(self, response_text: str | None = None, fail: bool = False) -> None:
        self._response_text = response_text
        self._fail = fail
        self.call_count = 0
        self.last_input_variables: dict[str, str] | None = None

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        max_tokens: int = 1000,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        self.call_count += 1
        self.last_input_variables = input_variables
        if self._fail:
            raise CareerCompassError("simulated provider failure")
        return self._response_text or "A sample answer."


def _make_question(tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs: object) -> InterviewQuestion:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        question="Tell me about yourself.",
        scope_target_role_ids=[None],
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return InterviewQuestion(**defaults)  # type: ignore[arg-type]


def _make_target_role(tenant_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> TargetRole:
    return TargetRole(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id, role_name=role_name, tag="X",
        created_at=datetime.now(UTC),
    )


class TestGenerateAnswer:
    async def test_generates_and_persists_an_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        topics_repo = FakeInterviewTopicRepository()
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({}))
        llm = FakeLLMService(response_text="  I once led a project that... ")

        service = InterviewAnswerService(questions_repo, topics_repo, career_profile, target_roles, llm)
        result = await service.generate_answer(
            tenant_id=tenant_id, user_id=user_id, question_id=question.id
        )

        assert result.ai_answer == "I once led a project that..."
        assert result.ai_answer_status == "generated"
        assert result.ai_answer_error is None
        assert result.ai_answer_generated_at is not None
        assert llm.call_count == 1

    async def test_grounds_the_prompt_in_the_target_role_name(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(tenant_id, user_id, scope_target_role_ids=[role.id])
        )
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({role.id: role}))
        llm = FakeLLMService()

        service = InterviewAnswerService(
            questions_repo, FakeInterviewTopicRepository(), career_profile, target_roles, llm
        )
        await service.generate_answer(tenant_id=tenant_id, user_id=user_id, question_id=question.id)

        assert llm.last_input_variables is not None
        assert "Staff Engineer" in llm.last_input_variables["role_context"]

    async def test_grounds_the_prompt_in_profile_competencies(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        profiles_repo = FakeCareerProfileRepository()
        now = datetime.now(UTC)
        await profiles_repo.create(
            CareerProfile(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                current_version=1,
                headline="Staff Engineer",
                summary=None,
                career_readiness_score=None,
                photo_url=None,
                core_competencies=[CoreCompetency(name="Python"), CoreCompetency(name="Leadership")],
                created_at=now,
                updated_at=now,
            )
        )
        career_profile = CareerProfileService(profiles_repo, FakeCareerProfileVersionRepository())
        target_roles = TargetRoleService(FakeTargetRoleRepository({}))
        llm = FakeLLMService()

        service = InterviewAnswerService(
            questions_repo, FakeInterviewTopicRepository(), career_profile, target_roles, llm
        )
        await service.generate_answer(tenant_id=tenant_id, user_id=user_id, question_id=question.id)

        assert llm.last_input_variables is not None
        assert "Python" in llm.last_input_variables["profile_context"]
        assert "Leadership" in llm.last_input_variables["profile_context"]

    async def test_grounds_the_prompt_in_linked_topic_discussion(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        topics_repo = FakeInterviewTopicRepository()
        topic = await topics_repo.create(
            InterviewTopic(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                name="System Design",
                blocks=[
                    ArticleBlock(
                        id=uuid.uuid4(),
                        columns=[
                            ArticleColumn(
                                id=uuid.uuid4(),
                                type="rich_text",
                                label="Notes",
                                html="Focus on trade-offs between consistency and availability.",
                            )
                        ],
                    )
                ],
                scope_target_role_ids=[None],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(tenant_id, user_id, topic_id=topic.id)
        )
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({}))
        llm = FakeLLMService()

        service = InterviewAnswerService(questions_repo, topics_repo, career_profile, target_roles, llm)
        await service.generate_answer(tenant_id=tenant_id, user_id=user_id, question_id=question.id)

        assert llm.last_input_variables is not None
        assert "consistency and availability" in llm.last_input_variables["topic_context"]

    async def test_follow_up_grounds_in_its_parents_role_and_topic_not_its_own(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        topics_repo = FakeInterviewTopicRepository()
        topic = await topics_repo.create(
            InterviewTopic(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                name="System Design",
                blocks=[
                    ArticleBlock(
                        id=uuid.uuid4(),
                        columns=[
                            ArticleColumn(
                                id=uuid.uuid4(),
                                type="rich_text",
                                label="Notes",
                                html="Focus on trade-offs between consistency and availability.",
                            )
                        ],
                    )
                ],
                scope_target_role_ids=[None],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        questions_repo = FakeInterviewQuestionRepository()
        parent = await questions_repo.create(
            _make_question(
                tenant_id,
                user_id,
                question="How do you approach system design?",
                scope_target_role_ids=[role.id],
                topic_id=topic.id,
            )
        )
        # A follow-up has no scope tags/topic_id of its own — this is the
        # real shape InterviewQuestionService.add_follow_up() produces.
        follow_up = await questions_repo.create(
            _make_question(
                tenant_id,
                user_id,
                question="Can you go deeper on that trade-off?",
                scope_target_role_ids=[],
                parent_question_id=parent.id,
            )
        )
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({role.id: role}))
        llm = FakeLLMService()

        service = InterviewAnswerService(questions_repo, topics_repo, career_profile, target_roles, llm)
        await service.generate_answer(tenant_id=tenant_id, user_id=user_id, question_id=follow_up.id)

        assert llm.last_input_variables is not None
        assert "Staff Engineer" in llm.last_input_variables["role_context"]
        assert "consistency and availability" in llm.last_input_variables["topic_context"]
        assert (
            'This is a follow-up to the earlier question: "How do you approach system design?"'
            in llm.last_input_variables["parent_question_context"]
        )
        # The literal question sent to the model is still the follow-up's
        # own text, not the parent's.
        assert llm.last_input_variables["question"] == "Can you go deeper on that trade-off?"

    async def test_top_level_question_has_no_parent_question_context(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(_make_question(tenant_id, user_id))
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({}))
        llm = FakeLLMService()

        service = InterviewAnswerService(
            questions_repo, FakeInterviewTopicRepository(), career_profile, target_roles, llm
        )
        await service.generate_answer(tenant_id=tenant_id, user_id=user_id, question_id=question.id)

        assert llm.last_input_variables is not None
        assert llm.last_input_variables["parent_question_context"] == ""

    async def test_failure_persists_failed_status_without_erasing_a_prior_answer(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        questions_repo = FakeInterviewQuestionRepository()
        question = await questions_repo.create(
            _make_question(
                tenant_id, user_id, ai_answer="A previously good answer.", ai_answer_status="generated"
            )
        )
        career_profile = CareerProfileService(
            FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
        )
        target_roles = TargetRoleService(FakeTargetRoleRepository({}))
        llm = FakeLLMService(fail=True)

        service = InterviewAnswerService(
            questions_repo, FakeInterviewTopicRepository(), career_profile, target_roles, llm
        )
        result = await service.generate_answer(
            tenant_id=tenant_id, user_id=user_id, question_id=question.id
        )

        assert result.ai_answer_status == "failed"
        assert result.ai_answer_error is not None
        assert result.ai_answer == "A previously good answer."
