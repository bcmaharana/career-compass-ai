"""Unit tests for TargetRoleService."""

from __future__ import annotations

import uuid

import pytest

from app.application.career_profile.target_role_service import MAX_TARGET_ROLES, TargetRoleService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import TargetRole


class FakeTargetRoleRepository:
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


@pytest.fixture
def service() -> tuple[TargetRoleService, FakeTargetRoleRepository]:
    target_roles = FakeTargetRoleRepository()
    return TargetRoleService(target_roles), target_roles


@pytest.mark.unit
class TestAddAndList:
    async def test_add_creates_a_target_role(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        target_role = await svc.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )

        assert target_role.role_name == "Staff Engineer"
        assert target_role.tag == "SE"

    async def test_tag_is_normalized_to_uppercase(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        target_role = await svc.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Enterprise Agile Coach", tag="eac"
        )

        assert target_role.tag == "EAC"

    async def test_list_only_returns_the_calling_users_target_roles(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()

        await svc.add(tenant_id=tenant_id, user_id=user_a, role_name="A's role", tag="A")
        await svc.add(tenant_id=tenant_id, user_id=user_b, role_name="B's role", tag="B")

        roles_for_a = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_a)

        assert len(roles_for_a) == 1
        assert roles_for_a[0].role_name == "A's role"

    async def test_rejects_a_target_role_past_the_limit(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        for i in range(MAX_TARGET_ROLES):
            await svc.add(tenant_id=tenant_id, user_id=user_id, role_name=f"Role {i}", tag="R")

        with pytest.raises(ValidationError) as exc_info:
            await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="One too many", tag="X")

        assert exc_info.value.code == "TARGET_ROLE_LIMIT_REACHED"


@pytest.mark.unit
class TestUpdate:
    async def test_owner_can_rename_and_retag(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(
            tenant_id=tenant_id, user_id=user_id, role_name="Staff Engineer", tag="SE"
        )

        updated = await svc.update(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role.id,
            role_name="Principal Engineer",
            tag="pe",
        )

        assert updated.role_name == "Principal Engineer"
        assert updated.tag == "PE"

    async def test_a_user_cannot_update_another_users_target_role(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(
            tenant_id=tenant_id, user_id=owner, role_name="Owner's role", tag="OR"
        )

        with pytest.raises(NotFoundError) as exc_info:
            await svc.update(
                tenant_id=tenant_id,
                user_id=intruder,
                target_role_id=target_role.id,
                role_name="Hijacked",
                tag="HJ",
            )

        assert exc_info.value.code == "TARGET_ROLE_NOT_FOUND"


@pytest.mark.unit
class TestDelete:
    async def test_a_user_cannot_delete_another_users_target_role(self, service) -> None:
        svc, target_roles = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(
            tenant_id=tenant_id, user_id=owner, role_name="Owner's role", tag="OR"
        )

        with pytest.raises(NotFoundError):
            await svc.delete(tenant_id=tenant_id, user_id=intruder, target_role_id=target_role.id)

        assert target_role.id in target_roles.target_roles

    async def test_owner_can_delete_their_own_target_role(self, service) -> None:
        svc, target_roles = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")

        await svc.delete(tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id)

        assert target_role.id not in target_roles.target_roles


@pytest.mark.unit
class TestRequiredSkills:
    async def test_add_required_skill_appends_trimmed_name(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")

        updated = await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="  SQL  "
        )

        assert updated.required_skills == ["SQL"]

    async def test_add_required_skill_dedupes_case_insensitively(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")

        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )
        updated = await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="python"
        )

        assert updated.required_skills == ["Python"]

    async def test_add_required_skill_rejects_blank_name(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")

        with pytest.raises(ValidationError) as exc_info:
            await svc.add_required_skill(
                tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="   "
            )

        assert exc_info.value.code == "REQUIRED_SKILL_NAME_REQUIRED"

    async def test_remove_required_skill(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )

        updated = await svc.remove_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="python"
        )

        assert updated.required_skills == []

    async def test_remove_required_skill_is_a_no_op_when_not_present(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")

        updated = await svc.remove_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Nothing"
        )

        assert updated.required_skills == []

    async def test_rename_required_skill_preserves_position(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="SQL"
        )
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Pyhton"
        )
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Docker"
        )

        updated = await svc.rename_required_skill(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role.id,
            old_name="Pyhton",
            new_name="Python",
        )

        assert updated.required_skills == ["SQL", "Python", "Docker"]

    async def test_rename_required_skill_rejects_collision_with_a_different_entry(
        self, service
    ) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="SQL"
        )

        with pytest.raises(ValidationError) as exc_info:
            await svc.rename_required_skill(
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role.id,
                old_name="SQL",
                new_name="python",
            )

        assert exc_info.value.code == "REQUIRED_SKILL_ALREADY_EXISTS"

    async def test_rename_required_skill_allows_unchanged_case_variation(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )

        updated = await svc.rename_required_skill(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role.id,
            old_name="Python",
            new_name="python",
        )

        assert updated.required_skills == ["python"]

    async def test_rename_required_skill_rejects_blank_name(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role = await svc.add(tenant_id=tenant_id, user_id=user_id, role_name="X", tag="X")
        await svc.add_required_skill(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id, name="Python"
        )

        with pytest.raises(ValidationError) as exc_info:
            await svc.rename_required_skill(
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role.id,
                old_name="Python",
                new_name="   ",
            )

        assert exc_info.value.code == "REQUIRED_SKILL_NAME_REQUIRED"
