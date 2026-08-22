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


class TogglePublicRequest(BaseModel):
    is_public: bool


class ShowcasePageResponse(BaseModel):
    id: UUID
    target_role_id: UUID
    is_public: bool
    blocks: list[ShowcaseBlockPayload]
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
