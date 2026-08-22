"""Showcase Page application service.

One page per Target Role (enforced by a DB UNIQUE constraint, mirrored
here by the same create-on-first-access race handling
CareerProfileService.get_or_create already established). A page's
`blocks` are seeded once, lazily, from that role's generated
tailored-resume content (ResumeExportService.gather_resume_data_with_master_fallback)
the first time the page is ever accessed — after that it's fully
independent and user-editable, including block order/labels, matching
the same "one-time copy, not a sync" precedent Master -> Target Role
Profile already established elsewhere in this app.

set_public() deliberately does NOT itself mint a public_share_links row
— that's PublicSharingService's job (app/application/showcase_page/
public_sharing_service.py), which composes this service with
PublicShareLinkService so a toggle-on both flips the flag and ensures a
reusable share key exists, while this service stays a plain CRUD layer
that doesn't need to know about share links at all.
"""

from __future__ import annotations

import html as html_lib
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from app.adapters.documents.resume_data import (
    ResumeData,
    education_degree_line,
    format_date_range,
    group_competencies_by_category,
)
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.resume_export_service import ResumeExportService
from app.application.career_profile.target_role_service import TargetRoleService
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.career_profile.storage import ObjectStorageRepository
from app.domain.showcase_page.entities import ShowcaseBlock, ShowcaseColumn, ShowcasePage
from app.domain.showcase_page.repositories import ShowcasePageRepository

ALLOWED_IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — same limit as profile photos / topic images
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_IMAGE_KEY_PREFIX = "showcase-pages/"


def showcase_block_image_key_from_url(image_url: str) -> str | None:
    """Reconstructs the storage key from a column's stored image_url —
    same "the key itself is never persisted separately" reasoning as
    app/application/career_profile/career_profile_service.py's
    photo_key_from_url, just locating the key by its known
    `showcase-pages/` prefix (upload_image's own key format) rather than
    reassembling it from tenant/profile/extension parts, since the
    column id needed to reassemble it isn't otherwise available at
    deletion time. Used by app/adapters/db/account_deletion.py for
    best-effort public-bucket cleanup on account deletion."""
    path = urlsplit(image_url).path
    idx = path.find(_IMAGE_KEY_PREFIX)
    return path[idx:] if idx != -1 else None


def _escape(text: str) -> str:
    return html_lib.escape(text, quote=False)


def _seed_blocks_from_resume_data(data: ResumeData) -> list[ShowcaseBlock]:
    """Turns a gathered resume's data into an initial, editable block
    list — one single-column rich_text row per non-empty resume section,
    in the same order a downloaded resume already presents them. Entry
    descriptions are embedded as-is (already sanitized rich HTML from
    their own save path — see app/core/rich_text.py's module docstring
    on "reads are trusted"); anything else interpolated here (titles,
    company names, dates) is plain text and is HTML-escaped.
    """
    blocks: list[ShowcaseBlock] = []

    def add(label: str, html: str) -> None:
        if html.strip():
            column = ShowcaseColumn(id=uuid.uuid4(), type="rich_text", label=label, html=html)
            blocks.append(ShowcaseBlock(id=uuid.uuid4(), columns=[column]))

    about = "".join(part for part in (data.profile.headline, data.profile.summary) if part)
    add("About", about)

    if data.profile.core_competencies:
        items = "".join(
            f"<li>{_escape(c.name)}</li>"
            for _, group in group_competencies_by_category(data.profile.core_competencies)
            for c in group
        )
        add("Core Competencies", f"<ul>{items}</ul>")

    if data.career_highlights:
        parts = [
            f"<p><strong>{_escape(item.title)}</strong></p>{item.description or ''}"
            for item in data.career_highlights
        ]
        add("Career Highlights", "".join(parts))

    if data.experiences:
        parts = []
        for exp in data.experiences:
            heading = f"<p><strong>{_escape(exp.title)} — {_escape(exp.company)}</strong>"
            if exp.location:
                heading += f" ({_escape(exp.location)})"
            date_range = _escape(format_date_range(exp.start_date, exp.end_date))
            heading += f"<br/><em>{date_range}</em></p>"
            parts.append(heading + (exp.description or ""))
        add("Experience", "".join(parts))

    if data.educations:
        parts = []
        for edu in data.educations:
            line = education_degree_line(edu)
            heading = f"<p><strong>{_escape(edu.institution)}</strong>"
            if line:
                heading += f"<br/>{_escape(line)}"
            heading += "</p>"
            parts.append(heading + (edu.description or ""))
        add("Education", "".join(parts))

    if data.certifications:
        parts = [
            f"<p><strong>{_escape(cert.name)}</strong> — {_escape(cert.issuing_organization)}</p>"
            for cert in data.certifications
        ]
        add("Certifications", "".join(parts))

    if data.key_achievements:
        parts = [
            f"<p><strong>{_escape(item.title)}</strong></p>{item.description or ''}"
            for item in data.key_achievements
        ]
        add("Key Achievements", "".join(parts))

    if data.career_goals:
        parts = [
            f"<p><strong>{_escape(item.target_role)}</strong></p>{item.description or ''}"
            for item in data.career_goals
        ]
        add("Career Goals", "".join(parts))

    if data.recommendations:
        parts = [
            f"<p><strong>{_escape(item.recommender_name)}</strong></p>{item.content}"
            for item in data.recommendations
        ]
        add("Recommendations", "".join(parts))

    return blocks


class ShowcasePageService:
    def __init__(
        self,
        pages: ShowcasePageRepository,
        target_roles: TargetRoleService,
        career_profiles: CareerProfileService,
        resume_export: ResumeExportService,
        storage: ObjectStorageRepository,
    ) -> None:
        self._pages = pages
        self._target_roles = target_roles
        self._career_profiles = career_profiles
        self._resume_export = resume_export
        self._storage = storage

    async def get_or_create(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> ShowcasePage:
        await self._target_roles.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing = await self._pages.get_by_target_role(tenant_id, target_role_id)
        if existing is not None:
            return existing

        # A Target Role's own CareerProfile row is only ever created
        # lazily (CareerProfileService.get_or_create, called by every
        # OTHER Career Profile section's own endpoint) — a role added
        # via TargetRoleService.add() alone has no CareerProfile row
        # yet. ResumeExportService._gather() 404s if one doesn't exist
        # (correct for its other callers, which always run after the
        # Career Profile page has already triggered that lazy create),
        # so ensure it here explicitly rather than depending on caller
        # ordering — a Showcase Page can otherwise be reached before
        # any other section's fetch has had the chance to create it.
        # Master's profile must exist too: gather_resume_data_with_master_fallback
        # unconditionally falls back to Master's own _gather() whenever
        # the target role's profile turns out empty (no headline/
        # summary/experiences — true for a freshly-created role), and
        # that fallback 404s just the same if Master doesn't exist yet.
        await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=None
        )
        await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        _profile, data = await self._resume_export.gather_resume_data_with_master_fallback(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        now = datetime.now(UTC)
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role_id,
            created_at=now,
            updated_at=now,
            is_public=False,
            blocks=_seed_blocks_from_resume_data(data),
        )
        try:
            return await self._pages.create(page)
        except ConflictError:
            # Lost a create-on-first-access race, same handling
            # CareerProfileService.get_or_create already established.
            winner = await self._pages.get_by_target_role(tenant_id, target_role_id)
            assert winner is not None, "the concurrent winner's row must exist after a create race"
            return winner

    async def update(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, blocks: list[ShowcaseBlock]
    ) -> ShowcasePage:
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        page.blocks = [
            replace(
                block,
                columns=[
                    replace(column, html=sanitize_rich_text(column.html))
                    if column.type == "rich_text"
                    else column
                    for column in block.columns
                ],
            )
            for block in blocks
        ]
        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def set_public(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, is_public: bool
    ) -> ShowcasePage:
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        page.is_public = is_public
        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def upload_image(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID,
        column_id: UUID,
        content: bytes,
        content_type: str,
    ) -> ShowcasePage:
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported image type '{content_type}'. Allowed: "
                f"{sorted(ALLOWED_IMAGE_CONTENT_TYPES)}",
                code="UNSUPPORTED_IMAGE_TYPE",
            )
        if len(content) > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError(
                f"Image exceeds the {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB limit.",
                code="IMAGE_TOO_LARGE",
            )
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        column = next(
            (col for block in page.blocks for col in block.columns if col.id == column_id), None
        )
        if column is None:
            raise NotFoundError("Showcase column not found.", code="SHOWCASE_COLUMN_NOT_FOUND")

        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        key = f"showcase-pages/{tenant_id}/{page.id}/{column_id}.{extension}"
        url = await self._storage.upload(key=key, content=content, content_type=content_type)
        # Cache-busting query param — same reasoning as
        # CareerProfileService.upload_photo (the storage key is stable
        # per column so re-uploads don't accumulate objects, which means
        # a stable URL the browser's image cache won't otherwise re-fetch).
        column.image_url = f"{url}?v={int(datetime.now(UTC).timestamp())}"

        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)
