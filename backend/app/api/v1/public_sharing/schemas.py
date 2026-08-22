"""Response schemas for the anonymous public-sharing API. Deliberately
separate from app/api/v1/showcase_page/schemas.py and
app/api/v1/interview_prep/schemas.py's own response shapes rather than
reusing them — those are authenticated, owner-facing shapes that will
keep evolving independently; this is a fixed, read-only, anonymous-safe
projection that should never accidentally grow an owner-only field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PublicReferenceLink(BaseModel):
    url: str
    label: str


class PublicShowcaseBlock(BaseModel):
    id: UUID
    type: Literal["rich_text", "image", "video_embed", "article_link", "external_link"]
    label: str
    html: str | None = None
    image_url: str | None = None
    video_embed_url: str | None = None
    #: The linked Article's OWN share_key — never the raw internal
    #: topic id (see PublicShowcasePageView.article_share_keys' own
    #: docstring for why). None whenever the link doesn't currently
    #: resolve to a public Article — the frontend renders that case as
    #: plain (non-linked) text.
    article_share_key: str | None = None
    external_url: str | None = None


class PublicShowcasePageResponse(BaseModel):
    owner_display_name: str
    owner_handle: str
    role_name: str
    role_tag: str
    blocks: list[PublicShowcaseBlock]
    updated_at: datetime


class PublicArticleResponse(BaseModel):
    owner_display_name: str
    owner_handle: str
    name: str
    discussion: str | None
    image_url: str | None
    reference_links: list[PublicReferenceLink]
