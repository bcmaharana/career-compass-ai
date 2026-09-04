"""Request/response schemas for the (authenticated) Showcase Page API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ShowcaseBlockTypePayload = Literal[
    "rich_text", "image", "video_embed", "article_link", "external_link"
]


class ShowcaseColumnPayload(BaseModel):
    id: UUID
    type: ShowcaseBlockTypePayload
    label: str
    html: str | None = None
    image_url: str | None = None
    video_embed_url: str | None = None
    article_topic_id: UUID | None = None
    external_url: str | None = None


class ShowcaseBlockPayload(BaseModel):
    id: UUID
    #: 1 or more columns rendered side by side (equal width) on desktop,
    #: stacked vertically on mobile — see ShowcaseBlock's own domain
    #: docstring for the full "why". No cap on column count.
    columns: list[ShowcaseColumnPayload]


class ShowcasePageUpdateRequest(BaseModel):
    blocks: list[ShowcaseBlockPayload]
    #: Top-bar fields (2026-08-24) — seeded once, then independently
    #: editable, same as `blocks`. See ShowcasePage's own domain
    #: docstring for the full "why", including why there's no photo
    #: field here at all (deliberately not editable from this page).
    name: str | None = None
    headline: str | None = None
    summary: str | None = None


class TogglePublicRequest(BaseModel):
    is_public: bool


class ShowcasePageResponse(BaseModel):
    id: UUID
    target_role_id: UUID
    is_public: bool
    blocks: list[ShowcaseBlockPayload]
    name: str | None
    headline: str | None
    summary: str | None
    #: Resolved fresh from the real, current CareerProfile on every
    #: response — never persisted on this page ("the profile picture
    #: will be fixed" — direct request, see ShowcasePage's own docstring).
    photo_url: str | None
    #: Page-level image the owner uploads directly (see ShowcasePage's
    #: own docstring) — None means the public page falls back to
    #: photo_url + Executive Summary side by side, same as before this
    #: field existed.
    background_image_url: str | None
    #: Original filename of the owner's uploaded resume document (PDF or
    #: Word), None if none has been uploaded. Kept for display only —
    #: the actual file lives in a private bucket, see resume_url.
    resume_file_name: str | None
    #: Fresh presigned URLs for the resume file above, resolved on every
    #: response rather than stored (a persisted URL would expire long
    #: before this page is re-fetched — see
    #: ShowcasePageService.get_resume_urls). Both None whenever
    #: resume_file_name is None. resume_view_url opens the file in place
    #: (inline disposition); resume_download_url saves it (attachment)
    #: — two separate URLs since one presigned URL can only carry one
    #: disposition.
    resume_view_url: str | None
    resume_download_url: str | None
    #: The public URL's last path segment, present whenever this page
    #: has ever been made public (even if currently toggled back off —
    #: see PublicShareLink's own docstring for why the key persists
    #: across toggle cycles). None only for a page that's never once
    #: been made public. The frontend composes the full pretty URL
    #: itself from the caller's own handle + this target role's tag +
    #: this key — see the owning migration's module docstring for why
    #: the API deliberately doesn't return a full URL.
    share_key: str | None
    created_at: datetime
    updated_at: datetime
