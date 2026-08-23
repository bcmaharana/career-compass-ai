"""Showcase Page domain entities.

A per-Target-Role, freeform public-sharing document (direct 2026-08-22
request) — deliberately NOT the Career Profile made public. Seeded once
from that role's generated tailored-resume content
(ResumeExportService.gather_resume_data_with_master_fallback), then fully
independent and user-editable afterward: content, labels, and order can
all diverge freely from the profile that seeded them, matching the same
"one-time copy, not a sync" precedent Master -> Target Role Profile
already established elsewhere in this app.

`blocks` is a single ordered list stored as one JSON column on the page
row, not a separate child table with its own repository/move() endpoints
— the list is small and bounded, and the whole thing is replaced
atomically on every save (same shape as CareerProfile.core_competencies /
resume_section_toggles), so reordering is just rewriting array order in
one `update()` call rather than per-row move() plumbing.

Every block is a ROW that can hold one or more COLUMNS side by side
(direct 2026-08-24 request: "in a row, put an image in the first column,
2nd column a paragraph, third one may be a video" — column count is
freely chosen per row, not a fixed layout). What used to be the block's
own single set of content fields (type/label/html/image_url/...) now
lives on each column instead — a block that's never been split still
works exactly the same, it's just a row with one column. Columns render
equal-width side by side on desktop and stacked vertically on mobile (no
per-column width customization — direct 2026-08-24 decision), and there's
no cap on how many columns a row can have.

`ShowcaseBlock`/`ShowcaseColumn` are this domain's own local names for
the generic `ContentBlock`/`ContentColumn` shape defined in
app/domain/content_blocks/entities.py (extracted 2026-08-24 once
InterviewTopic/Article needed the identical shape) — re-exported here so
every existing call site in this domain keeps reading `ShowcaseBlock`
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domain.content_blocks.entities import ContentBlock as ShowcaseBlock
from app.domain.content_blocks.entities import ContentColumn as ShowcaseColumn
from app.domain.content_blocks.entities import ContentColumnType as ShowcaseBlockType

__all__ = [
    "ShowcaseBlock",
    "ShowcaseColumn",
    "ShowcaseBlockType",
    "ShowcasePage",
    "ShareableResourceType",
    "PublicShareLink",
]


@dataclass(slots=True)
class ShowcasePage:
    """Exactly one per TargetRole (enforced by a DB UNIQUE constraint on
    target_role_id, not just application logic) — capped implicitly by
    the existing MAX_TARGET_ROLES limit (TargetRoleService), so this
    entity needs no cap of its own. Auto-provisioned lazily via
    ShowcasePageService.get_or_create, the same pattern
    CareerProfileService.get_or_create already established.

    `name`/`headline`/`summary` (2026-08-24 top-bar request) are seeded
    once at creation from the owning User's display_name and the
    resolved CareerProfile's headline/summary (same Master-fallback
    source `blocks` itself is seeded from), then fully independent and
    user-editable afterward — the same "seed once, not a sync"
    precedent every other piece of this page's content already follows.
    Unlike `blocks`, there is deliberately no photo field here at all:
    the profile picture is NOT copied/editable on this page ("the
    profile picture will be fixed" — direct request), it always reflects
    whatever the real CareerProfile's current photo is, resolved fresh
    on every read via ShowcasePageService.get_photo_url/
    PublicShowcaseService's own equivalent, never persisted here.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role_id: UUID
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    blocks: list[ShowcaseBlock] = field(default_factory=list)
    name: str | None = None
    headline: str | None = None
    summary: str | None = None


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
