"""Unit tests for GapAnalysisService (simplified per ADR-005).

Owned skills come from CareerProfile.core_competencies; required skills
come from TargetRole.required_skills — both plain free-text lists, matched
case-insensitively.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.skill_intelligence.gap_analysis_service import GapAnalysisService
from app.domain.career_profile.entities import CareerProfile, TargetRole


class FakeCareerProfileRepository:
    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def get_by_user_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if profile.tenant_id == tenant_id and profile.user_id == user_id:
                return replace(profile)
        return None

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeCareerProfileVersionRepository:
    async def create(self, version: object) -> object:
        return version


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.target_roles: dict[uuid.UUID, TargetRole] = {}

    async def create(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = replace(target_role)
        return replace(target_role)

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        target_role = self.target_roles.get(target_role_id)
        return replace(target_role) if target_role and target_role.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[TargetRole]:
        return [
            replace(r)
            for r in self.target_roles.values()
            if r.tenant_id == tenant_id and r.user_id == user_id
        ]

    async def update(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = replace(target_role)
        return replace(target_role)

    async def soft_delete(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> None:
        self.target_roles.pop(target_role_id, None)


@pytest.fixture
def service() -> GapAnalysisService:
    career_profiles = CareerProfileService(
        FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()  # type: ignore[arg-type]
    )
    target_roles = TargetRoleService(FakeTargetRoleRepository())
    return GapAnalysisService(career_profiles, target_roles)


@pytest.mark.unit
class TestGapAnalysisService:
    async def test_missing_required_skills_produce_a_gap(self, service: GapAnalysisService) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await service._career_profiles.update(
            tenant_id=tenant_id,
            user_id=user_id,
            headline=None,
            summary=None,
            core_competencies=["Python"],
        )
        target_role = await service._target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )
        await service._target_roles.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )
        await service._target_roles.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="SQL"
        )

        result = await service.compute(tenant_id=tenant_id, user_id=user_id)

        assert len(result.target_role_gaps) == 1
        gap = result.target_role_gaps[0]
        assert gap.target_role_id == target_role.id
        assert gap.role_name == "Staff Engineer"
        assert gap.tag == "SE"
        assert gap.missing_skills == ["SQL"]

    async def test_matching_is_case_insensitive(self, service: GapAnalysisService) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await service._career_profiles.update(
            tenant_id=tenant_id,
            user_id=user_id,
            headline=None,
            summary=None,
            core_competencies=["python"],
        )
        target_role = await service._target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )
        await service._target_roles.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="PYTHON"
        )

        result = await service.compute(tenant_id=tenant_id, user_id=user_id)

        assert result.target_role_gaps == []

    async def test_no_gap_when_target_role_has_no_required_skills(
        self, service: GapAnalysisService
    ) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await service._target_roles.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )

        result = await service.compute(tenant_id=tenant_id, user_id=user_id)

        assert result.target_role_gaps == []
