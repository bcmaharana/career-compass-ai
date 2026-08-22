"""Showcase Page domain entities.

A per-Target-Role, freeform public-sharing document (direct 2026-08-22
request) — deliberately NOT the Career Profile made public. Seeded once
from that role's generated tailored-resume content
(ResumeExportService.gather_resume_data_with_master_fallback), then fully
independent and user-editable afterward: block content, block labels, and
block order can all diverge freely from the profile that seeded them,
matching the same "one-time copy, not a sync" precedent Master -> Target
Role Profile already established elsewhere in this app.

`blocks` is a single ordered list stored as one JSON column on the page
row, not a separate child table with its own repository/move() endpoints
— the list is small and bounded, and the whole thing is replaced
atomically on every save (same shape as CareerProfile.core_competencies /
resume_section_toggles), so reordering is just rewriting array order in
one `update()` call rather than per-row move() plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

#: Kept intentionally small — enough to build a cover-letter-style page
#: (prose, a photo, a video walkthrough, links out to public Articles or
#: anywhere else) without becoming a general-purpose page builder.
ShowcaseBlockType = Literal["rich_text", "image", "video_embed", "article_link", "external_link"]


@dataclass(slots=True)
class ShowcaseBlock:
    """One section of a Showcase Page. Every block carries a user-editable
    `label` (the whole point of "freeform, including labels") plus exactly
    one populated content field, chosen by `type` — the others stay None
    for that block. Sanitization of `html` happens in the application
    service (ShowcasePageService.update), the same enforcement-point
    convention app/core/rich_text.py's own docstring establishes for every
    other rich-text field in this app: reads are trusted because every
    write path already went through sanitize_rich_text.
    """

    id: UUID
    type: ShowcaseBlockType
    label: str
    html: str | None = None
    #: A bare, non-expiring public URL (app/domain/career_profile/storage.py's
    #: ObjectStorageRepository.upload() already returns one directly — this
    #: field stores that return value as-is, not a storage key to resolve
    #: later, unlike Interview Prep's private-bucket image_key which needs a
    #: fresh presigned URL generated on every read).
    image_url: str | None = None
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
class ShowcasePage:
    """Exactly one per TargetRole (enforced by a DB UNIQUE constraint on
    target_role_id, not just application logic) — capped implicitly by
    the existing MAX_TARGET_ROLES limit (TargetRoleService), so this
    entity needs no cap of its own. Auto-provisioned lazily via
    ShowcasePageService.get_or_create, the same pattern
    CareerProfileService.get_or_create already established.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role_id: UUID
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    blocks: list[ShowcaseBlock] = field(default_factory=list)


#: Resource types a public_share_links row can point at — kept as a
#: literal here (not a DB reference table) since there are only ever two
#: and they never vary per tenant, same reasoning as
#: app/domain/platform_admin/permissions.py's plain constant tuple.
ShareableResourceType = Literal["showcase_page", "interview_topic"]


@dataclass(slots=True)
class PublicShareLink:
    """The RLS-exempt cross-tenant lookup this whole feature turns on —
    same "must be resolvable before any tenant context exists" reasoning
    as personal_phone_logins/password_reset_tokens, just for anonymous
    content viewing instead of login. See the owning migration's module
    docstring for the full design rationale.

    `share_key` is the primary key and the literal last path segment of
    the public URL — a long, unguessable, cryptographically random token
    (secrets.token_urlsafe, generated once in
    PublicShareLinkService.get_or_create_key) that is the ENTIRE access
    control boundary for the resource it points at. `resource_type` +
    `resource_id` together identify exactly one row in exactly one other
    (RLS-protected) table; `tenant_id` is denormalized here specifically
    so an anonymous request can learn it without first being able to
    query the tenant-owned table the resource actually lives in.

    Deliberately never deleted when a resource is toggled private — a
    UNIQUE (resource_type, resource_id) constraint means a resource is
    only ever issued one key for its whole lifetime, so re-enabling public
    sharing later reuses the exact same URL rather than minting a new one
    (direct 2026-08-22 requirement). The *live* is_public flag on the
    resource itself (not this table) is what actually gates whether an
    anonymous request gets served or 404s.
    """

    share_key: str
    tenant_id: UUID
    resource_type: ShareableResourceType
    resource_id: UUID
    user_id: UUID
    created_at: datetime
