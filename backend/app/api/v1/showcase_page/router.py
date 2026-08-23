"""Showcase Page API routes (authenticated side).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Own dedicated router/
prefix (/api/v1/showcase-pages), not folded into career_profile's
router — target_role_id is always required here (a Showcase Page has no
Master-profile equivalent), unlike that router's optional-query-param
Master-vs-Target-Role convention.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile

from app.api.dependencies import (
    get_current_identity,
    get_public_share_link_service,
    get_public_sharing_service,
    get_showcase_page_service,
)
from app.api.v1.showcase_page.schemas import (
    ShowcaseBlockPayload,
    ShowcaseColumnPayload,
    ShowcasePageResponse,
    ShowcasePageUpdateRequest,
    TogglePublicRequest,
)
from app.application.showcase_page.public_share_link_service import PublicShareLinkService
from app.application.showcase_page.public_sharing_service import PublicSharingService
from app.application.showcase_page.showcase_page_service import ShowcasePageService
from app.core.identity_provider_interface import IdentityClaims
from app.domain.showcase_page.entities import ShowcaseBlock, ShowcaseColumn, ShowcasePage

router = APIRouter(tags=["showcase-page"])


def _column_payload(column: ShowcaseColumn) -> ShowcaseColumnPayload:
    return ShowcaseColumnPayload(
        id=column.id,
        type=column.type,
        label=column.label,
        html=column.html,
        image_url=column.image_url,
        video_embed_url=column.video_embed_url,
        article_topic_id=column.article_topic_id,
        external_url=column.external_url,
    )


def _column_from_payload(column: ShowcaseColumnPayload) -> ShowcaseColumn:
    return ShowcaseColumn(
        id=column.id,
        type=column.type,
        label=column.label,
        html=column.html,
        image_url=column.image_url,
        video_embed_url=column.video_embed_url,
        article_topic_id=column.article_topic_id,
        external_url=column.external_url,
    )


async def _page_response(
    page: ShowcasePage, service: ShowcasePageService, share_links: PublicShareLinkService
) -> ShowcasePageResponse:
    share_key = await share_links.get_existing_key(
        resource_type="showcase_page", resource_id=page.id
    )
    photo_url = await service.get_photo_url(
        tenant_id=page.tenant_id, user_id=page.user_id, target_role_id=page.target_role_id
    )
    return ShowcasePageResponse(
        id=page.id,
        target_role_id=page.target_role_id,
        is_public=page.is_public,
        blocks=[
            ShowcaseBlockPayload(
                id=block.id,
                columns=[_column_payload(column) for column in block.columns],
            )
            for block in page.blocks
        ],
        name=page.name,
        headline=page.headline,
        summary=page.summary,
        photo_url=photo_url,
        share_key=share_key,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


@router.get("/showcase-pages/{target_role_id}", response_model=ShowcasePageResponse)
async def get_showcase_page(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ShowcasePageService = Depends(get_showcase_page_service),
    share_links: PublicShareLinkService = Depends(get_public_share_link_service),
) -> ShowcasePageResponse:
    page = await service.get_or_create(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return await _page_response(page, service, share_links)


@router.patch("/showcase-pages/{target_role_id}", response_model=ShowcasePageResponse)
async def update_showcase_page(
    target_role_id: UUID,
    request: ShowcasePageUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ShowcasePageService = Depends(get_showcase_page_service),
    share_links: PublicShareLinkService = Depends(get_public_share_link_service),
) -> ShowcasePageResponse:
    blocks = [
        ShowcaseBlock(
            id=block.id,
            columns=[_column_from_payload(column) for column in block.columns],
        )
        for block in request.blocks
    ]
    page = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        blocks=blocks,
        name=request.name,
        headline=request.headline,
        summary=request.summary,
    )
    return await _page_response(page, service, share_links)


@router.post("/showcase-pages/{target_role_id}/toggle-public", response_model=ShowcasePageResponse)
async def toggle_showcase_page_public(
    target_role_id: UUID,
    request: TogglePublicRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PublicSharingService = Depends(get_public_sharing_service),
    showcase_pages: ShowcasePageService = Depends(get_showcase_page_service),
    share_links: PublicShareLinkService = Depends(get_public_share_link_service),
) -> ShowcasePageResponse:
    page, _share_key = await service.set_showcase_page_public(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        is_public=request.is_public,
    )
    return await _page_response(page, showcase_pages, share_links)


@router.post(
    "/showcase-pages/{target_role_id}/columns/{column_id}/image",
    response_model=ShowcasePageResponse,
)
async def upload_showcase_column_image(
    target_role_id: UUID,
    column_id: UUID,
    file: UploadFile,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ShowcasePageService = Depends(get_showcase_page_service),
    share_links: PublicShareLinkService = Depends(get_public_share_link_service),
) -> ShowcasePageResponse:
    content = await file.read()
    page = await service.upload_image(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        column_id=column_id,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )
    return await _page_response(page, service, share_links)
