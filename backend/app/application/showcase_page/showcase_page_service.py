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
import re
import uuid
from dataclasses import dataclass, replace
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
from app.core.exceptions import CareerCompassError, ConflictError, NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.career_profile.storage import ObjectStorageRepository
from app.domain.identity.repositories import UserRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.entities import ShowcaseBlock, ShowcaseColumn, ShowcasePage
from app.domain.showcase_page.repositories import ShowcasePageRepository

ALLOWED_IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — same limit as profile photos / topic images
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_IMAGE_KEY_PREFIX = "showcase-pages/"

# Same allowed set/extension mapping as resume_intelligence's own upload
# (app/application/resume_intelligence/resume_extraction_service.py) —
# PDF or Word only, no legacy .doc. No parsing happens on this file at
# all (unlike that other upload path), so nothing here cares about
# content beyond its declared type.
ALLOWED_RESUME_CONTENT_TYPES = frozenset(
    {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
)
_RESUME_EXTENSION_BY_CONTENT_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10MB — same limit as resume_intelligence's own upload
_RESUME_KEY_PREFIX = "showcase-resumes/"
# Same reasoning as ResumeExportService's own _DOWNLOAD_URL_TTL_SECONDS —
# this URL is meant to sit on a persistent public page, not a one-shot
# immediate-use link, so it needs to outlive resume_intelligence's 300s.
RESUME_DOWNLOAD_URL_TTL_SECONDS = 3600

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


@dataclass(slots=True)
class ResumeUrls:
    view_url: str | None
    download_url: str | None


def resume_download_filename(*, display_name: str, extension: str) -> str:
    """The presigned URL's ResponseContentDisposition filename — computed
    fresh from the current owner display name on every read (same
    "recompute at request time, never bake into storage" reasoning as
    ResumeExportService's own _resume_filename), so a later name change
    is reflected immediately without touching the stored file. Shared by
    both ShowcasePageService (authenticated) and PublicShowcaseService
    (anonymous) rather than duplicated, since both need the exact same
    filename for the exact same underlying file.
    """
    safe_name = _UNSAFE_FILENAME_CHARS.sub(" ", display_name).strip() or "Resume"
    return f"{safe_name} Resume.{extension}"


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
        users: UserRepository,
        resume_storage: PrivateObjectStorageRepository,
    ) -> None:
        self._pages = pages
        self._target_roles = target_roles
        self._career_profiles = career_profiles
        self._resume_export = resume_export
        self._storage = storage
        self._users = users
        # Same concrete S3ObjectStorageRepository instance as `storage`
        # above (structurally satisfies both Protocols against two
        # different buckets — see that adapter's own module docstring),
        # just typed against the private-bucket Protocol for the resume
        # file methods (upload_private/get_presigned_url/delete_private)
        # that ObjectStorageRepository doesn't declare. Same two-param
        # convention ResumeExportService/DeleteAccountService already use
        # for public-vs-private storage.
        self._resume_storage = resume_storage

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
        profile, data = await self._resume_export.gather_resume_data_with_master_fallback(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        # Top-bar fields (2026-08-24), seeded once alongside `blocks` from
        # the same already-resolved (Master-fallback-aware) profile — see
        # ShowcasePage's own docstring for why there's no photo field
        # here at all.
        user = await self._users.get_by_id(tenant_id, user_id)
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
            name=user.display_name if user else None,
            headline=profile.headline,
            summary=profile.summary,
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
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID,
        blocks: list[ShowcaseBlock],
        name: str | None,
        headline: str | None,
        summary: str | None,
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
        # name is plain text (a person's name, rendered as plain text on
        # both the editor and the public page — never dangerouslySetInnerHTML),
        # so it doesn't go through sanitize_rich_text; headline/summary
        # are rich text like every other such field in this app.
        stripped_name = name.strip() if name else ""
        page.name = stripped_name or None
        page.headline = sanitize_rich_text(headline)
        page.summary = sanitize_rich_text(summary)
        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def get_photo_url(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> str | None:
        """The profile picture is deliberately "fixed" (direct request)
        — never copied onto the Showcase Page itself, always resolved
        fresh from the real, current CareerProfile, with the same
        Master-fallback a Target Role Profile with no photo of its own
        already gets for its seeded block content."""
        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        if profile.photo_url:
            return profile.photo_url
        master = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=None
        )
        return master.photo_url

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

    async def upload_background_image(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID,
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

        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        # Stable key per page (not per upload) — same cache-busting-
        # query-param reasoning as upload_image/CareerProfileService.upload_photo.
        key = f"{_IMAGE_KEY_PREFIX}{tenant_id}/{page.id}/background.{extension}"
        url = await self._storage.upload(key=key, content=content, content_type=content_type)
        page.background_image_url = f"{url}?v={int(datetime.now(UTC).timestamp())}"

        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def remove_background_image(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> ShowcasePage:
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        if page.background_image_url is not None:
            key = showcase_block_image_key_from_url(page.background_image_url)
            if key is not None:
                try:
                    await self._storage.delete(key=key)
                except CareerCompassError:
                    # Best-effort, same "DB field is the source of truth"
                    # reasoning as CareerProfileService.delete_photo.
                    pass

        page.background_image_url = None
        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def upload_resume(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> ShowcasePage:
        if content_type not in ALLOWED_RESUME_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported resume type '{content_type}'. Allowed: PDF, DOCX.",
                code="UNSUPPORTED_RESUME_TYPE",
            )
        if len(content) > MAX_RESUME_SIZE_BYTES:
            raise ValidationError(
                f"Resume exceeds the {MAX_RESUME_SIZE_BYTES // (1024 * 1024)}MB limit.",
                code="RESUME_TOO_LARGE",
            )
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )

        extension = _RESUME_EXTENSION_BY_CONTENT_TYPE[content_type]
        # Stable key per page (not per upload, and not keyed by extension)
        # — a re-upload in the other format overwrites in place rather
        # than accumulating a stale file the new one doesn't replace,
        # same "one file per owner" model as background_image_url.
        key = f"{_RESUME_KEY_PREFIX}{tenant_id}/{page.id}/resume.{extension}"
        if page.resume_file_key is not None and page.resume_file_key != key:
            try:
                await self._resume_storage.delete_private(key=page.resume_file_key)
            except CareerCompassError:
                pass
        await self._resume_storage.upload_private(
            key=key, content=content, content_type=content_type
        )
        page.resume_file_key = key
        page.resume_file_name = filename

        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def remove_resume(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> ShowcasePage:
        page = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        if page.resume_file_key is not None:
            try:
                await self._resume_storage.delete_private(key=page.resume_file_key)
            except CareerCompassError:
                # Best-effort, same "DB field is the source of truth"
                # reasoning as remove_background_image.
                pass

        page.resume_file_key = None
        page.resume_file_name = None
        page.updated_at = datetime.now(UTC)
        return await self._pages.update(page)

    async def get_resume_urls(
        self, *, tenant_id: UUID, user_id: UUID, page: ShowcasePage
    ) -> ResumeUrls:
        """Fresh presigned URLs for the owner's own resume file, resolved
        on every read rather than stored — same reasoning as
        ResumeExportService.get_download_urls (a persisted presigned URL
        would expire long before the page is re-fetched). Two separate
        URLs, not one: "View" opens the file in place (inline
        disposition) and "Download" saves it (attachment) — a single
        presigned URL can only carry one disposition, since S3's SigV4
        signature is computed over the full query string including
        ResponseContentDisposition (see get_presigned_url's own
        docstring)."""
        if page.resume_file_key is None:
            return ResumeUrls(view_url=None, download_url=None)
        user = await self._users.get_by_id(tenant_id, user_id)
        display_name = user.display_name if user and user.display_name else "Resume"
        extension = page.resume_file_key.rsplit(".", 1)[-1]
        filename = resume_download_filename(display_name=display_name, extension=extension)
        view_url = await self._resume_storage.get_presigned_url(
            key=page.resume_file_key,
            expires_in_seconds=RESUME_DOWNLOAD_URL_TTL_SECONDS,
            download_filename=filename,
            disposition="inline",
        )
        download_url = await self._resume_storage.get_presigned_url(
            key=page.resume_file_key,
            expires_in_seconds=RESUME_DOWNLOAD_URL_TTL_SECONDS,
            download_filename=filename,
            disposition="attachment",
        )
        return ResumeUrls(view_url=view_url, download_url=download_url)
