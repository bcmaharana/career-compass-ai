"""Unit tests for CareerGoalService."""

from __future__ import annotations

import uuid

import pytest

from app.application.career_profile.career_goal_service import CareerGoalService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import CareerGoal


class FakeCareerGoalRepository:
    def __init__(self) -> None:
        self.goals: dict[uuid.UUID, CareerGoal] = {}

    async def create(self, goal: CareerGoal) -> CareerGoal:
        self.goals[goal.id] = goal
        return goal

    async def get_by_id(self, tenant_id: uuid.UUID, goal_id: uuid.UUID) -> CareerGoal | None:
        goal = self.goals.get(goal_id)
        return goal if goal and goal.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[CareerGoal]:
        return [
            g for g in self.goals.values() if g.tenant_id == tenant_id and g.user_id == user_id
        ]

    async def update(self, goal: CareerGoal) -> CareerGoal:
        self.goals[goal.id] = goal
        return goal

    async def soft_delete(self, tenant_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        self.goals.pop(goal_id, None)


@pytest.fixture
def service() -> tuple[CareerGoalService, FakeCareerGoalRepository]:
    goals = FakeCareerGoalRepository()
    return CareerGoalService(goals), goals


@pytest.mark.unit
class TestAddAndList:
    async def test_add_creates_a_goal_with_active_status(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        goal = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role="Staff Engineer",
            target_date=None,
            description=None,
        )

        assert goal.status == "active"
        assert goal.target_role == "Staff Engineer"

    async def test_list_only_returns_the_calling_users_goals(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()

        await svc.add(
            tenant_id=tenant_id,
            user_id=user_a,
            target_role="A's goal",
            target_date=None,
            description=None,
        )
        await svc.add(
            tenant_id=tenant_id,
            user_id=user_b,
            target_role="B's goal",
            target_date=None,
            description=None,
        )

        goals_for_a = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_a)

        assert len(goals_for_a) == 1
        assert goals_for_a[0].target_role == "A's goal"


@pytest.mark.unit
class TestUpdate:
    async def test_rejects_an_invalid_status(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        goal = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role="X",
            target_date=None,
            description=None,
        )

        with pytest.raises(ValidationError) as exc_info:
            await svc.update(
                tenant_id=tenant_id,
                user_id=user_id,
                goal_id=goal.id,
                target_role="X",
                target_date=None,
                status="not_a_real_status",
                description=None,
            )

        assert exc_info.value.code == "INVALID_GOAL_STATUS"

    async def test_a_user_cannot_update_another_users_goal(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()
        goal = await svc.add(
            tenant_id=tenant_id,
            user_id=owner,
            target_role="Owner's goal",
            target_date=None,
            description=None,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await svc.update(
                tenant_id=tenant_id,
                user_id=intruder,
                goal_id=goal.id,
                target_role="Hijacked",
                target_date=None,
                status="active",
                description=None,
            )

        assert exc_info.value.code == "CAREER_GOAL_NOT_FOUND"


@pytest.mark.unit
class TestDelete:
    async def test_a_user_cannot_delete_another_users_goal(self, service) -> None:
        svc, goals = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()
        goal = await svc.add(
            tenant_id=tenant_id,
            user_id=owner,
            target_role="Owner's goal",
            target_date=None,
            description=None,
        )

        with pytest.raises(NotFoundError):
            await svc.delete(tenant_id=tenant_id, user_id=intruder, goal_id=goal.id)

        # Confirm the goal is untouched, not just that an error was raised.
        assert goal.id in goals.goals

    async def test_owner_can_delete_their_own_goal(self, service) -> None:
        svc, goals = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        goal = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role="X",
            target_date=None,
            description=None,
        )

        await svc.delete(tenant_id=tenant_id, user_id=user_id, goal_id=goal.id)

        assert goal.id not in goals.goals
