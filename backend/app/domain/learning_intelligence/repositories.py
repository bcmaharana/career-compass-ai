"""Repository interfaces for the Learning Intelligence bounded context.

Application services depend only on these Protocols — see
app/domain/career_profile/repositories.py for the established pattern
this follows.
"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from app.domain.learning_intelligence.entities import LearningItem, LearningRecommendationSet

#: Declared locally, not imported from app.adapters.db.reorder — domain/
#: must have zero adapter imports. Same duplication precedent as
#: app/domain/career_profile/repositories.py's own Direction alias.
Direction = Literal["up", "down"]


class LearningItemRepository(Protocol):
    async def create(self, item: LearningItem) -> LearningItem: ...
    async def get_by_id(self, tenant_id: UUID, item_id: UUID) -> LearningItem | None: ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[LearningItem]: ...
    async def update(self, item: LearningItem) -> LearningItem: ...
    async def soft_delete(self, tenant_id: UUID, item_id: UUID) -> None: ...
    async def move(self, tenant_id: UUID, item_id: UUID, direction: Direction) -> None: ...


class LearningRecommendationRepository(Protocol):
    async def get_for_target_role(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> LearningRecommendationSet | None: ...
    async def upsert(self, rec_set: LearningRecommendationSet) -> LearningRecommendationSet:
        """Insert a new row, or overwrite the existing one for the same
        (tenant_id, user_id, target_role_id) — never accumulates
        history."""
        ...
