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

from app.api.dependencies import (
    get_public_certification_service,
    get_public_profile_skill_service,
    get_public_showcase_service,
)
from app.api.v1.career_profile.schemas import (
    PublicCertificationResponse,
    PublicProfileSkillResponse,
)
from app.api.v1.public_sharing.schemas import (
    PublicArticleBlock,
    PublicArticleColumn,
    PublicArticleResponse,
    PublicShowcaseBlock,
    PublicShowcaseColumn,
    PublicShowcasePageResponse,
)
from app.application.career_profile.public_certification_service import (
    PublicCertificationService,
)
from app.application.career_profile.public_profile_skill_service import (
    PublicProfileSkillService,
)
from app.application.showcase_page.public_showcase_service import PublicShowcaseService
from app.core.url_validation import safe_http_url

router = APIRouter(prefix="/public", tags=["public-sharing"])

_NOT_FOUND_DETAIL = "This page doesn't exist or is no longer public."


@router.get("/certificates/{share_key}", response_model=PublicCertificationResponse)
async def get_public_certificate(
    share_key: str,
    service: PublicCertificationService = Depends(get_public_certification_service),
) -> PublicCertificationResponse:
    view = await service.get_certificate(share_key)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    certification = view.certification
    return PublicCertificationResponse(
        owner_display_name=view.owner_display_name,
        name=certification.name,
        issuing_organization=certification.issuing_organization,
        issue_date=certification.issue_date,
        expiration_date=certification.expiration_date,
        does_not_expire=certification.does_not_expire,
        credential_id=certification.credential_id,
        credential_url=safe_http_url(certification.credential_url),
        certificate_file_name=certification.certificate_file_name,
        certificate_file_content_type=certification.certificate_file_content_type,
        certificate_file_url=view.certificate_file_url,
        badge_image_url=view.badge_image_url,
        badge_url=safe_http_url(certification.badge_url),
    )


@router.get("/skills/{share_key}", response_model=PublicProfileSkillResponse)
async def get_public_profile_skill(
    share_key: str,
    service: PublicProfileSkillService = Depends(get_public_profile_skill_service),
) -> PublicProfileSkillResponse:
    view = await service.get_skill(share_key)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    skill = view.profile_skill
    return PublicProfileSkillResponse(
        owner_display_name=view.owner_display_name,
        name=skill.name,
        issuing_organization=skill.issuing_organization,
        issue_date=skill.issue_date,
        expiration_date=skill.expiration_date,
        does_not_expire=skill.does_not_expire,
        credential_id=skill.credential_id,
        credential_url=safe_http_url(skill.credential_url),
        skill_file_name=skill.skill_file_name,
        skill_file_content_type=skill.skill_file_content_type,
        skill_file_url=view.skill_file_url,
        badge_image_url=view.badge_image_url,
        badge_url=safe_http_url(skill.badge_url),
    )


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
        owner_first_name=view.owner_first_name,
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
                        show_background=column.show_background,
                        background_color=column.background_color,
                        html=column.html,
                        diagram_data=column.diagram_data,
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
                        show_background=column.show_background,
                        background_color=column.background_color,
                        html=column.html,
                        diagram_data=column.diagram_data,
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
