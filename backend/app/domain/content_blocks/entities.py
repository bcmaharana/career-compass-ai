"""Generic freeform content-block model, shared by every domain that lets
a user compose a page/document out of typed content pieces — currently
ShowcasePage (app/domain/showcase_page) and InterviewTopic/"Article"
(app/domain/interview_prep). Extracted here (2026-08-24) once the second
consumer needed the exact same shape, rather than duplicating it or
letting one domain's naming leak into the other — both domains import
and re-export these under their own local names
(app/domain/showcase_page/entities.py's `ShowcaseBlock`/`ShowcaseColumn`,
app/domain/interview_prep/entities.py's `ArticleBlock`/`ArticleColumn`),
so nothing about either domain's own vocabulary changes at any call site.

A ContentBlock is a ROW that can hold one or more ContentColumns side by
side (direct 2026-08-24 request: "in a row, put an image in the first
column, 2nd column a paragraph, third one may be a video" — column count
is freely chosen per row, not a fixed layout). A row with just one column
is the common case and looks identical to a plain single-item block.
Columns render equal-width side by side on desktop and stacked vertically
on mobile (no per-column width customization — direct 2026-08-24
decision), and there's no cap on how many columns a row can have.

`blocks` is always stored as a single ordered list in one JSON column on
the owning row, not a separate child table with its own repository/move()
endpoints — the list is small and bounded per page/document, and the
whole thing is replaced atomically on every save (same shape as
CareerProfile.core_competencies/resume_section_toggles), so reordering is
just rewriting array order in one `update()` call rather than per-row
move() plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

#: Kept intentionally small — enough to build a cover-letter-style page
#: (prose, a photo, a video walkthrough, links out to public Articles or
#: anywhere else) without becoming a general-purpose page builder.
ContentColumnType = Literal["rich_text", "image", "video_embed", "article_link", "external_link"]


@dataclass(slots=True)
class ContentColumn:
    """One column within a ContentBlock row. Carries a user-editable
    `label` (the whole point of "freeform, including labels") plus exactly
    one populated content field, chosen by `type` — the others stay None
    for that column. Sanitization of `html` happens in the owning
    application service (e.g. ShowcasePageService.update), the same
    enforcement-point convention app/core/rich_text.py's own docstring
    establishes for every other rich-text field in this app: reads are
    trusted because every write path already went through
    sanitize_rich_text.
    """

    id: UUID
    type: ContentColumnType
    label: str
    html: str | None = None
    #: A bare, non-expiring public URL for a public-bucket domain
    #: (ShowcasePage) — persisted as-is. For a private-bucket domain
    #: (Article/InterviewTopic), this field is never persisted at all;
    #: it's populated transiently at read time by resolving `image_key`
    #: to a fresh short-TTL presigned URL (same "never store a presigned
    #: URL, it goes stale" rule this app already applies to Resume
    #: Intelligence/Career Profile downloads).
    image_url: str | None = None
    #: Private-bucket storage key (Article/InterviewTopic only) — never
    #: set for ShowcasePage's own public-bucket columns, which have no
    #: separate key at all (see
    #: showcase_page_service.showcase_block_image_key_from_url, which
    #: reconstructs one from image_url instead of persisting it).
    image_key: str | None = None
    #: A ready-to-embed URL (e.g. "https://www.youtube.com/embed/XXXX") —
    #: the user pastes an embed URL directly rather than this app parsing
    #: an arbitrary watch-page URL into one; no video upload/storage of
    #: our own (direct 2026-08-22 decision — no new video infra).
    video_embed_url: str | None = None
    #: Points at one of this user's own InterviewTopic rows — only
    #: meaningful (and only ever rendered as a real link) once that topic
    #: is itself public; a page referencing a topic that's since gone
    #: private just renders as plain text on the public page rather than a
    #: broken/private link.
    article_topic_id: UUID | None = None
    external_url: str | None = None


@dataclass(slots=True)
class ContentBlock:
    """One row, holding 1+ ContentColumns side by side. `columns` is
    never empty in practice — the owning application service always
    collapses a row down to deleting it entirely once its last column is
    removed, the same "removing the only X removes the whole thing" rule
    InterviewTopic's multi-scope delete already established.
    """

    id: UUID
    columns: list[ContentColumn] = field(default_factory=list)
