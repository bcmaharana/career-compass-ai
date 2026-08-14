"""Career goal application service.

Goals are scoped directly by user_id (not career_profile_id) — see
docs/architecture data model. Ownership check follows the same
not-found-not-forbidden reasoning as ExperienceService.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import CareerGoal
from app.domain.career_profile.repositories import CareerGoalRepository, Direction

VALID_STATUSES = frozenset({"active", "achieved", "abandoned"})


class CareerGoalService:
    def __init__(self, goals: CareerGoalRepository) -> None:
        self._goals = goals

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, goal_id: UUID
    ) -> CareerGoal:
        goal = await self._goals.get_by_id(tenant_id, goal_id)
        if goal is None or goal.user_id != user_id:
            raise NotFoundError("Career goal not found.", code="CAREER_GOAL_NOT_FOUND")
        return goal

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role: str,
        target_date: date | None,
        description: str | None,
    ) -> CareerGoal:
        now = datetime.now(UTC)
        return await self._goals.create(
            CareerGoal(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role=target_role,
                target_date=target_date,
                status="active",
                description=description,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(self, *, tenant_id: UUID, user_id: UUID) -> list[CareerGoal]:
        return await self._goals.list_for_user(tenant_id, user_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        goal_id: UUID,
        target_role: str,
        target_date: date | None,
        status: str,
        description: str | None,
        include_in_resume: bool = True,
    ) -> CareerGoal:
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"status must be one of {sorted(VALID_STATUSES)}", code="INVALID_GOAL_STATUS"
            )

        goal = await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, goal_id=goal_id)
        goal.target_role = target_role
        goal.target_date = target_date
        goal.status = status
        goal.description = description
        goal.include_in_resume = include_in_resume
        return await self._goals.update(goal)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, goal_id: UUID) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, goal_id=goal_id)
        await self._goals.soft_delete(tenant_id, goal_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, goal_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, goal_id=goal_id)
        await self._goals.move(tenant_id, goal_id, direction)

    async def clear_all(self, *, tenant_id: UUID, user_id: UUID) -> None:
        await self._goals.soft_delete_all_for_user(tenant_id, user_id)
