"""Unit tests for LearningRecommendationService — fake repositories/LLM,
no database, no real LLM calls. Mirrors the fake-repository pattern
established in tests/unit/test_target_role_service.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.application.career_profile.target_role_service import TargetRoleService
from app.application.learning_intelligence.learning_recommendation_service import (
    LearningRecommendationService,
)
from app.application.skill_intelligence.gap_analysis_service import (
    GapAnalysisResult,
    TargetRoleGap,
)
from app.core.exceptions import CareerCompassError
from app.domain.career_profile.entities import TargetRole
from app.domain.learning_intelligence.entities import LearningRecommendationSet

pytestmark = pytest.mark.unit


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


class FakeGapAnalysisService:
    def __init__(self, result: GapAnalysisResult) -> None:
        self._result = result

    async def compute(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> GapAnalysisResult:
        return self._result


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
        return self._response_text or ""


class FakeLearningRecommendationRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], LearningRecommendationSet] = {}

    async def get_for_target_role(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> LearningRecommendationSet | None:
        return self.rows.get((tenant_id, user_id, target_role_id))

    async def upsert(self, rec_set: LearningRecommendationSet) -> LearningRecommendationSet:
        key = (rec_set.tenant_id, rec_set.user_id, rec_set.target_role_id)
        self.rows[key] = rec_set
        return rec_set


def _make_target_role(tenant_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> TargetRole:
    return TargetRole(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_name=role_name,
        tag="X",
        created_at=datetime.now(UTC),
    )


def _valid_llm_response() -> str:
    return json.dumps(
        {
            "recommendations": [
                {"skill": "Python", "resources": ["Course A", "Book B"], "summary": "Matters."},
            ]
        }
    )


class TestGetOrGenerate:
    async def test_generates_and_caches_recommendations(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()

        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )
        result = await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.status == "generated"
        assert result.recommendations == [
            {"skill": "Python", "resources": ["Course A", "Book B"], "summary": "Matters."}
        ]
        assert llm.call_count == 1

    async def test_serves_from_cache_within_ttl_and_matching_hash(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )

        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )
        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert llm.call_count == 1

    async def test_regenerates_when_missing_skills_change(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )
        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        # Gap analysis result changes — cache must be treated as stale.
        gap_analysis._result = GapAnalysisResult(
            target_role_gaps=[
                TargetRoleGap(
                    target_role_id=target_role.id,
                    role_name="Staff Engineer",
                    tag="X",
                    missing_skills=["Python", "SQL"],
                )
            ]
        )
        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert llm.call_count == 2

    async def test_force_regenerate_bypasses_cache(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )
        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        await service.get_or_generate(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role.id,
            force_regenerate=True,
        )

        assert llm.call_count == 2

    async def test_no_missing_skills_short_circuits_without_calling_llm(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )

        result = await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.status == "generated"
        assert result.recommendations == []
        assert llm.call_count == 0

    async def test_provider_failure_persists_a_failed_status(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(fail=True)
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )

        result = await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.status == "failed"
        assert result.recommendations is None
        assert result.error_message is not None

    async def test_malformed_json_persists_a_failed_status(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=["Python"],
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text="not json at all")
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )

        result = await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.status == "failed"

    async def test_caps_skills_sent_to_the_llm_prompt(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = _make_target_role(tenant_id, user_id, "Staff Engineer")
        target_roles_repo = FakeTargetRoleRepository({target_role.id: target_role})
        many_skills = [f"Skill{i}" for i in range(20)]
        gap = TargetRoleGap(
            target_role_id=target_role.id,
            role_name="Staff Engineer",
            tag="X",
            missing_skills=many_skills,
        )
        gap_analysis = FakeGapAnalysisService(GapAnalysisResult(target_role_gaps=[gap]))
        llm = FakeLLMService(response_text=_valid_llm_response())
        repo = FakeLearningRecommendationRepository()
        service = LearningRecommendationService(
            repo, gap_analysis, llm, TargetRoleService(target_roles_repo)
        )

        await service.get_or_generate(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert llm.last_input_variables is not None
        sent_skills = llm.last_input_variables["missing_skills"].split(", ")
        assert len(sent_skills) == 12
