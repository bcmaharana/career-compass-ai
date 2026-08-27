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


class PublicShowcaseColumn(BaseModel):
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


class PublicShowcaseBlock(BaseModel):
    id: UUID
    #: Rendered side by side (equal width) on desktop, stacked vertically
    #: on mobile — see ShowcaseBlock's own domain docstring.
    columns: list[PublicShowcaseColumn]


class PublicShowcasePageResponse(BaseModel):
    owner_display_name: str
    owner_handle: str
    role_name: str
    role_tag: str
    #: Top-bar fields (2026-08-24: profile picture on the left, name +
    #: headline and the executive summary on the right) — the page's own
    #: independent, editable copy (see ShowcasePage's own docstring),
    #: except photo_url which is never stored here at all, always
    #: resolved fresh from the real CareerProfile ("the profile picture
    #: will be fixed" — direct request).
    name: str | None
    headline: str | None
    summary: str | None
    photo_url: str | None
    #: See ShowcasePageResponse's own field of the same name — when set,
    #: the public page renders this as the top card's background image
    #: (with Executive Summary moved into its own card below) instead of
    #: the photo_url + Executive Summary side-by-side fallback layout.
    background_image_url: str | None
    blocks: list[PublicShowcaseBlock]
    updated_at: datetime


class PublicArticleColumn(BaseModel):
    id: UUID
    type: Literal["rich_text", "image", "video_embed", "article_link", "external_link"]
    label: str
    html: str | None = None
    image_url: str | None = None
    video_embed_url: str | None = None
    #: Another Article's OWN share_key (an Article can link to another
    #: one) — same "never the raw internal topic id, None whenever it
    #: doesn't currently resolve to a public Article" rule as
    #: PublicShowcaseColumn.article_share_key.
    article_share_key: str | None = None
    external_url: str | None = None


class PublicArticleBlock(BaseModel):
    id: UUID
    #: Rendered side by side (equal width) on desktop, stacked vertically
    #: on mobile — see ContentBlock's own domain docstring.
    columns: list[PublicArticleColumn]


class PublicArticleResponse(BaseModel):
    owner_display_name: str
    owner_handle: str
    name: str
    blocks: list[PublicArticleBlock]
