"""SQLAlchemy repository implementations for the Showcase Page /
public-sharing bounded context. See
app/adapters/db/models/showcase_page.py's module docstring for why
PublicShareLinkModel's repository never filters by tenant_id.
"""

from __future__ import annotations

import uuid
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models.showcase_page import PublicShareLinkModel, ShowcasePageModel
from app.core.exceptions import ConflictError
from app.domain.showcase_page.entities import (
    PublicShareLink,
    ShareableResourceType,
    ShowcaseBlock,
    ShowcaseColumn,
    ShowcasePage,
)


def _column_to_json(column: ShowcaseColumn) -> dict[str, Any]:
    return {
        "id": str(column.id),
        "type": column.type,
        "label": column.label,
        "html": column.html,
        "image_url": column.image_url,
        "video_embed_url": column.video_embed_url,
        "article_topic_id": str(column.article_topic_id) if column.article_topic_id else None,
        "external_url": column.external_url,
    }


def _column_from_json(item: dict[str, Any]) -> ShowcaseColumn:
    return ShowcaseColumn(
        id=uuid.UUID(item["id"]),
        type=item["type"],
        label=item["label"],
        html=item.get("html"),
        image_url=item.get("image_url"),
        video_embed_url=item.get("video_embed_url"),
        article_topic_id=(
            uuid.UUID(item["article_topic_id"]) if item.get("article_topic_id") else None
        ),
        external_url=item.get("external_url"),
    )


def _blocks_to_json(blocks: list[ShowcaseBlock]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(block.id),
            "columns": [_column_to_json(column) for column in block.columns],
        }
        for block in blocks
    ]


def _blocks_from_json(raw: list[dict[str, Any]]) -> list[ShowcaseBlock]:
    return [
        ShowcaseBlock(
            id=uuid.UUID(item["id"]),
            columns=[_column_from_json(column) for column in item["columns"]],
        )
        for item in raw
    ]


def _page_to_domain(model: ShowcasePageModel) -> ShowcasePage:
    return ShowcasePage(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        target_role_id=model.target_role_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        is_public=model.is_public,
        blocks=_blocks_from_json(model.blocks),
        name=model.name,
        headline=model.headline,
        summary=model.summary,
    )


class SqlAlchemyShowcasePageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, page: ShowcasePage) -> ShowcasePage:
        model = ShowcasePageModel(
            id=page.id,
            tenant_id=page.tenant_id,
            user_id=page.user_id,
            target_role_id=page.target_role_id,
            is_public=page.is_public,
            blocks=_blocks_to_json(page.blocks),
            name=page.name,
            headline=page.headline,
            summary=page.summary,
        )
        try:
            # SAVEPOINT, not a plain flush — same create-on-first-access
            # race handling as SqlAlchemyCareerProfileRepository.create
            # (several requests can independently call get_or_create for
            # a role's page in parallel), and a plain session.rollback()
            # would also discard the RLS tenant-context GUC.
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as e:
            if "uq_showcase_pages_target_role_id" not in str(e.orig):
                raise
            raise ConflictError(
                "A showcase page for this target role already exists.",
                code="SHOWCASE_PAGE_ALREADY_EXISTS",
            ) from e
        await self._session.refresh(model)
        return _page_to_domain(model)

    async def get_by_target_role(
        self, tenant_id: UUID, target_role_id: UUID
    ) -> ShowcasePage | None:
        result = await self._session.execute(
            select(ShowcasePageModel).where(
                ShowcasePageModel.tenant_id == tenant_id,
                ShowcasePageModel.target_role_id == target_role_id,
            )
        )
        model = result.scalar_one_or_none()
        return _page_to_domain(model) if model else None

    async def get_by_id(self, tenant_id: UUID, page_id: UUID) -> ShowcasePage | None:
        result = await self._session.execute(
            select(ShowcasePageModel).where(
                ShowcasePageModel.tenant_id == tenant_id,
                ShowcasePageModel.id == page_id,
            )
        )
        model = result.scalar_one_or_none()
        return _page_to_domain(model) if model else None

    async def update(self, page: ShowcasePage) -> ShowcasePage:
        model = await self._session.get(ShowcasePageModel, page.id)
        assert model is not None, "update() called with a page id that no longer exists"
        model.is_public = page.is_public
        model.blocks = _blocks_to_json(page.blocks)
        model.name = page.name
        model.headline = page.headline
        model.summary = page.summary
        await self._session.flush()
        await self._session.refresh(model)
        return _page_to_domain(model)


class SqlAlchemyPublicShareLinkRepository:
    """Deliberately never filters by tenant_id in get_by_key — this
    table is the RLS-exempt cross-tenant lookup an anonymous request
    resolves through before any tenant context exists, same shape as
    SqlAlchemyPersonalPhoneLoginRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, share_key: str) -> PublicShareLink | None:
        model = await self._session.get(PublicShareLinkModel, share_key)
        if model is None:
            return None
        return PublicShareLink(
            share_key=model.share_key,
            tenant_id=model.tenant_id,
            resource_type=cast(ShareableResourceType, model.resource_type),
            resource_id=model.resource_id,
            user_id=model.user_id,
            created_at=model.created_at,
        )

    async def get_by_resource(
        self, resource_type: ShareableResourceType, resource_id: UUID
    ) -> PublicShareLink | None:
        result = await self._session.execute(
            select(PublicShareLinkModel).where(
                PublicShareLinkModel.resource_type == resource_type,
                PublicShareLinkModel.resource_id == resource_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return PublicShareLink(
            share_key=model.share_key,
            tenant_id=model.tenant_id,
            resource_type=cast(ShareableResourceType, model.resource_type),
            resource_id=model.resource_id,
            user_id=model.user_id,
            created_at=model.created_at,
        )

    async def create(self, link: PublicShareLink) -> PublicShareLink:
        model = PublicShareLinkModel(
            share_key=link.share_key,
            tenant_id=link.tenant_id,
            resource_type=link.resource_type,
            resource_id=link.resource_id,
            user_id=link.user_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return PublicShareLink(
            share_key=model.share_key,
            tenant_id=model.tenant_id,
            resource_type=cast(ShareableResourceType, model.resource_type),
            resource_id=model.resource_id,
            user_id=model.user_id,
            created_at=model.created_at,
        )
