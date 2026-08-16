"""Unit tests for LearningItemService — fake repository, no database.
Mirrors tests/unit/test_target_role_service.py's fake-repository pattern.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.learning_intelligence.learning_item_service import LearningItemService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.learning_intelligence.entities import LearningItem

pytestmark = pytest.mark.unit


class FakeLearningItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, LearningItem] = {}
        self._next_order = 1

    async def create(self, item: LearningItem) -> LearningItem:
        item.display_order = self._next_order
        self._next_order += 1
        self.items[item.id] = item
        return item

    async def get_by_id(self, tenant_id: uuid.UUID, item_id: uuid.UUID) -> LearningItem | None:
        item = self.items.get(item_id)
        return item if item and item.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[LearningItem]:
        items = [
            i for i in self.items.values() if i.tenant_id == tenant_id and i.user_id == user_id
        ]
        return sorted(items, key=lambda i: i.display_order)

    async def update(self, item: LearningItem) -> LearningItem:
        self.items[item.id] = item
        return item

    async def soft_delete(self, tenant_id: uuid.UUID, item_id: uuid.UUID) -> None:
        self.items.pop(item_id, None)

    async def move(self, tenant_id: uuid.UUID, item_id: uuid.UUID, direction) -> None:
        items = await self.list_for_user(
            tenant_id, next(i.user_id for i in self.items.values() if i.id == item_id)
        )
        index = next(i for i, it in enumerate(items) if it.id == item_id)
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(items):
            return
        current, neighbor = items[index], items[neighbor_index]
        current.display_order, neighbor.display_order = (
            neighbor.display_order,
            current.display_order,
        )


@pytest.fixture
def service() -> tuple[LearningItemService, FakeLearningItemRepository]:
    repo = FakeLearningItemRepository()
    return LearningItemService(repo), repo


class TestAddAndList:
    async def test_add_creates_an_item_in_planned_status(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        item = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="Deep Learning Spec",
            provider="Coursera",
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        assert item.title == "Deep Learning Spec"
        assert item.status == "planned"

    async def test_add_rejects_blank_title(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        with pytest.raises(ValidationError):
            await svc.add(
                tenant_id=tenant_id,
                user_id=user_id,
                title="   ",
                provider=None,
                url=None,
                target_role_id=None,
                notes=None,
                started_at=None,
            )

    async def test_list_only_returns_current_users_items(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        await svc.add(
            tenant_id=tenant_id,
            user_id=user_a,
            title="A's item",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )
        await svc.add(
            tenant_id=tenant_id,
            user_id=user_b,
            title="B's item",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        result = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_a)

        assert [i.title for i in result] == ["A's item"]


class TestUpdate:
    async def test_update_changes_status_and_dates(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        item = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="X",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        updated = await svc.update(
            tenant_id=tenant_id,
            user_id=user_id,
            item_id=item.id,
            title="X",
            provider=None,
            url=None,
            status="completed",
            target_role_id=None,
            notes="done",
            started_at=None,
            completed_at=datetime.now(UTC).date(),
        )

        assert updated.status == "completed"
        assert updated.notes == "done"

    async def test_update_rejects_invalid_status(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        item = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="X",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        with pytest.raises(ValidationError):
            await svc.update(
                tenant_id=tenant_id,
                user_id=user_id,
                item_id=item.id,
                title="X",
                provider=None,
                url=None,
                status="bogus",
                target_role_id=None,
                notes=None,
                started_at=None,
                completed_at=None,
            )

    async def test_cannot_update_another_users_item(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        item = await svc.add(
            tenant_id=tenant_id,
            user_id=owner,
            title="X",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        with pytest.raises(NotFoundError):
            await svc.update(
                tenant_id=tenant_id,
                user_id=other,
                item_id=item.id,
                title="Y",
                provider=None,
                url=None,
                status="planned",
                target_role_id=None,
                notes=None,
                started_at=None,
                completed_at=None,
            )


class TestDeleteAndMove:
    async def test_delete_removes_the_item(self, service) -> None:
        svc, repo = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        item = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="X",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        await svc.delete(tenant_id=tenant_id, user_id=user_id, item_id=item.id)

        assert item.id not in repo.items

    async def test_move_swaps_display_order(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        first = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="First",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )
        second = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            title="Second",
            provider=None,
            url=None,
            target_role_id=None,
            notes=None,
            started_at=None,
        )

        await svc.move(tenant_id=tenant_id, user_id=user_id, item_id=second.id, direction="up")
        result = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_id)

        assert [i.title for i in result] == ["Second", "First"]
        assert first.id  # sanity: fixture ran
