"""Learning log application service (Phase 7).

Items are scoped directly by user_id (not career_profile_id) — same
shape/reasoning as CareerGoalService. Ownership check follows the same
not-found-not-forbidden reasoning as every other career-profile-style
service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.learning_intelligence.entities import LearningItem
from app.domain.learning_intelligence.repositories import Direction, LearningItemRepository

VALID_STATUSES = frozenset({"planned", "in_progress", "completed"})


class LearningItemService:
    def __init__(self, items: LearningItemRepository) -> None:
        self._items = items

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, item_id: UUID
    ) -> LearningItem:
        item = await self._items.get_by_id(tenant_id, item_id)
        if item is None or item.user_id != user_id:
            raise NotFoundError("Learning item not found.", code="LEARNING_ITEM_NOT_FOUND")
        return item

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        title: str,
        provider: str | None,
        url: str | None,
        target_role_id: UUID | None,
        notes: str | None,
        started_at: date | None,
    ) -> LearningItem:
        trimmed = title.strip()
        if not trimmed:
            raise ValidationError("Title is required.", code="LEARNING_ITEM_TITLE_REQUIRED")

        now = datetime.now(UTC)
        return await self._items.create(
            LearningItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                title=trimmed,
                provider=provider,
                url=url,
                status="planned",
                notes=sanitize_rich_text(notes),
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
                target_role_id=target_role_id,
                started_at=started_at,
            )
        )

    async def list_for_current_user(self, *, tenant_id: UUID, user_id: UUID) -> list[LearningItem]:
        return await self._items.list_for_user(tenant_id, user_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        item_id: UUID,
        title: str,
        provider: str | None,
        url: str | None,
        status: str,
        target_role_id: UUID | None,
        notes: str | None,
        started_at: date | None,
        completed_at: date | None,
    ) -> LearningItem:
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"status must be one of {sorted(VALID_STATUSES)}",
                code="INVALID_LEARNING_ITEM_STATUS",
            )
        trimmed = title.strip()
        if not trimmed:
            raise ValidationError("Title is required.", code="LEARNING_ITEM_TITLE_REQUIRED")

        item = await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        item.title = trimmed
        item.provider = provider
        item.url = url
        item.status = status
        item.target_role_id = target_role_id
        item.notes = sanitize_rich_text(notes)
        item.started_at = started_at
        item.completed_at = completed_at
        return await self._items.update(item)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, item_id: UUID) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        await self._items.soft_delete(tenant_id, item_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, item_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, item_id=item_id)
        await self._items.move(tenant_id, item_id, direction)
