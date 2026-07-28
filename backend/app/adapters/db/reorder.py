"""Shared move-up/move-down reordering logic.

Every orderable entity (Experience, Education, Certification,
CareerGoal, CareerHighlight, KeyAchievement, PeerEndorsement) has the
exact same reordering shape: a `display_order` integer column, scoped by
tenant plus either career_profile_id or user_id. Rather than duplicating
the swap logic seven times, every repository's `move()` method delegates
to this one function.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

Direction = Literal["up", "down"]


async def move_item(
    session: AsyncSession,
    model_cls: type[Any],
    *,
    tenant_id: UUID,
    scope_filter: ColumnElement[bool],
    item_id: UUID,
    direction: Direction,
) -> None:
    """Swap the target item's display_order with its neighbor in the
    requested direction, among non-deleted items in the given scope.

    `scope_filter` is the caller-supplied condition narrowing to "this
    profile's items" or "this user's items" (e.g.
    `ExperienceModel.career_profile_id == profile_id`) — kept generic
    here since different entities scope by different columns.

    `model_cls` is typed `type[Any]` rather than a Protocol describing
    the shared columns (id, tenant_id, deleted_at, display_order):
    SQLAlchemy declarative classes expose these as `InstrumentedAttribute`
    descriptors at the class level, not the plain instance-level types a
    Protocol would check against, so a Protocol here fights the ORM
    rather than describing it. This is exactly the SQLAlchemy
    dynamic-typing friction app/adapters/db's mypy override already
    exists for (see backend-architecture.md) — `Any` here is the same
    trade-off, applied narrowly to this one helper.
    """
    from sqlalchemy import select

    result = await session.execute(
        select(model_cls)
        .where(
            model_cls.tenant_id == tenant_id,
            scope_filter,
            model_cls.deleted_at.is_(None),
        )
        .order_by(model_cls.display_order.asc())
    )
    items = list(result.scalars().all())

    index = next((i for i, item in enumerate(items) if item.id == item_id), None)
    if index is None:
        return  # caller's ownership check (get_by_id) already guards this

    neighbor_index = index - 1 if direction == "up" else index + 1
    if neighbor_index < 0 or neighbor_index >= len(items):
        return  # already at the boundary — nothing to do

    current_item = items[index]
    neighbor_item = items[neighbor_index]
    current_item.display_order, neighbor_item.display_order = (
        neighbor_item.display_order,
        current_item.display_order,
    )
    await session.flush()


async def next_display_order(
    session: AsyncSession,
    model_cls: type[Any],
    *,
    tenant_id: UUID,
    scope_filter: ColumnElement[bool],
) -> int:
    """Returns 1 + the current max display_order in scope (0 if empty),
    so new items are appended to the end of the list by default.
    """
    from sqlalchemy import func, select

    result = await session.execute(
        select(func.max(model_cls.display_order)).where(
            model_cls.tenant_id == tenant_id,
            scope_filter,
        )
    )
    current_max = result.scalar_one_or_none()
    return (current_max or 0) + 1
