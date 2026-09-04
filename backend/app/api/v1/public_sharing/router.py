"""Anonymous public-sharing API routes.

The first genuinely public (zero-auth-dependency) FEATURE router in this
codebase — no Depends(get_current_identity) anywhere. See
app/application/showcase_page/public_showcase_service.py's module
docstring for the tenant-resolution mechanics this depends on.

A share key that doesn't resolve to a live, currently-public resource
(never existed, wrong resource type, or toggled back to private) is a
plain 404 — never a distinguishing error, matching
PublicShowcaseService's own "an anonymous caller must not be able to
tell these apart" contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_public_showcase_service
from app.api.v1.public_sharing.schemas import (
    PublicArticleBlock,
    PublicArticleColumn,
    PublicArticleResponse,
    PublicShowcaseBlock,
    PublicShowcaseColumn,
    PublicShowcasePageResponse,
)
from app.application.showcase_page.public_showcase_service import PublicShowcaseService

router = APIRouter(prefix="/public", tags=["public-sharing"])

_NOT_FOUND_DETAIL = "This page doesn't exist or is no longer public."


@router.get("/showcase-pages/{share_key}", response_model=PublicShowcasePageResponse)
async def get_public_showcase_page(
    share_key: str,
    service: PublicShowcaseService = Depends(get_public_showcase_service),
) -> PublicShowcasePageResponse:
    view = await service.get_showcase_page(share_key)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    return PublicShowcasePageResponse(
        owner_display_name=view.owner_display_name,
        owner_handle=view.owner_handle,
        role_name=view.role_name,
        role_tag=view.role_tag,
        name=view.page.name,
        headline=view.page.headline,
        summary=view.page.summary,
        photo_url=view.photo_url,
        background_image_url=view.page.background_image_url,
        resume_view_url=view.resume_view_url,
        resume_download_url=view.resume_download_url,
        blocks=[
            PublicShowcaseBlock(
                id=block.id,
                columns=[
                    PublicShowcaseColumn(
                        id=column.id,
                        type=column.type,
                        label=column.label,
                        html=column.html,
                        image_url=column.image_url,
                        video_embed_url=column.video_embed_url,
                        article_share_key=(
                            view.article_share_keys.get(column.article_topic_id)
                            if column.article_topic_id is not None
                            else None
                        ),
                        external_url=column.external_url,
                    )
                    for column in block.columns
                ],
            )
            for block in view.page.blocks
        ],
        updated_at=view.page.updated_at,
    )


@router.get("/articles/{share_key}", response_model=PublicArticleResponse)
async def get_public_article(
    share_key: str,
    service: PublicShowcaseService = Depends(get_public_showcase_service),
) -> PublicArticleResponse:
    view = await service.get_article(share_key)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    return PublicArticleResponse(
        owner_display_name=view.owner_display_name,
        owner_handle=view.owner_handle,
        name=view.topic.name,
        blocks=[
            PublicArticleBlock(
                id=block.id,
                columns=[
                    PublicArticleColumn(
                        id=column.id,
                        type=column.type,
                        label=column.label,
                        html=column.html,
                        image_url=view.image_urls.get(column.id),
                        video_embed_url=column.video_embed_url,
                        article_share_key=(
                            view.article_share_keys.get(column.article_topic_id)
                            if column.article_topic_id is not None
                            else None
                        ),
                        external_url=column.external_url,
                    )
                    for column in block.columns
                ],
            )
            for block in view.topic.blocks
        ],
    )
