"""Generates and persists a downloadable resume document (DOCX or PDF)
from a CareerProfile's current data.

Reuses the exact set of child repositories ClearCareerProfileService
already fans out to (read-only here). The generated file replaces any
previously generated file of the *same format* for this profile — same
one-file-per-profile-per-format model as CareerProfileService's
photo_url (regenerating overwrites, it does not accumulate a history) —
stored in the private resumes bucket resume_intelligence's
upload-and-parse flow already established (app/adapters/storage/s3_object_storage.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from app.adapters.documents.resume_data import ResumeData
from app.adapters.documents.resume_docx_builder import build_resume_docx
from app.adapters.documents.resume_pdf_builder import build_resume_pdf
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import (
    CareerGoal,
    CareerHighlight,
    CareerProfile,
    Certification,
    Education,
    Experience,
    KeyAchievement,
    PeerEndorsement,
    TargetRole,
)
from app.domain.career_profile.repositories import CareerProfileRepository
from app.domain.identity.entities import User
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository

ResumeFormat = Literal["docx", "pdf"]

_T = TypeVar("_T")  # invariant — list[_T] (like every mutable container) can't use a covariant one


class _ProfileScopedReader(Protocol[_T]):
    """The one method ResumeExportService actually needs from each of
    Experience/Education/Certification/CareerHighlight/KeyAchievement's
    full repository Protocols — read-only, so a fake covering just this
    method is enough for tests, and the real per-domain repositories
    (which have far more methods: create/update/soft_delete/...)
    structurally satisfy this narrower Protocol without any change.
    """

    async def list_for_profile(self, tenant_id: UUID, career_profile_id: UUID) -> list[_T]: ...


class _UserScopedReader(Protocol[_T]):
    """The read-only counterpart of _ProfileScopedReader for CareerGoal,
    which is scoped by user_id rather than career_profile_id — see
    CareerGoal's own entity docstring.
    """

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[_T]: ...


class _TargetRoleReader(Protocol):
    async def get_by_id(self, tenant_id: UUID, target_role_id: UUID) -> TargetRole | None: ...


class _UserReader(Protocol):
    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None: ...

_CONTENT_TYPES: dict[ResumeFormat, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

# Unlike resume_intelligence's presigned URLs (300s, single immediate
# use right after upload), this URL is meant to sit on the Career
# Profile page as a persistent "View Resume" link — 1 hour balances a
# realistic page-dwell time against not leaving a link to a private
# document valid indefinitely.
_DOWNLOAD_URL_TTL_SECONDS = 3600

# Anything that isn't a safe cross-OS filename character — collapsed to
# a single space rather than dropped outright, so "Jordan / Rivera"
# doesn't become "JordanRivera".
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


def _safe_filename_part(text: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub(" ", text).strip()


def _resume_filename(*, display_name: str, role_label: str | None, format: ResumeFormat) -> str:
    parts = [_safe_filename_part(display_name)]
    if role_label:
        parts.append(_safe_filename_part(role_label))
    parts.append("Resume")
    return f"{' - '.join(parts)}.{format}"


@dataclass(slots=True)
class ResumeDownloadUrls:
    docx_url: str | None
    pdf_url: str | None


class ResumeExportService:
    def __init__(
        self,
        profiles: CareerProfileRepository,
        experiences: _ProfileScopedReader[Experience],
        educations: _ProfileScopedReader[Education],
        certifications: _ProfileScopedReader[Certification],
        career_highlights: _ProfileScopedReader[CareerHighlight],
        key_achievements: _ProfileScopedReader[KeyAchievement],
        career_goals: _UserScopedReader[CareerGoal],
        peer_endorsements: _ProfileScopedReader[PeerEndorsement],
        target_roles: _TargetRoleReader,
        users: _UserReader,
        storage: PrivateObjectStorageRepository,
    ) -> None:
        self._profiles = profiles
        self._experiences = experiences
        self._educations = educations
        self._certifications = certifications
        self._career_highlights = career_highlights
        self._key_achievements = key_achievements
        self._career_goals = career_goals
        self._peer_endorsements = peer_endorsements
        self._target_roles = target_roles
        self._users = users
        self._storage = storage

    def _section_enabled(self, profile: CareerProfile, section_key: str) -> bool:
        """A missing key (including a profile that's never set any
        toggle at all) means "on" — see
        CareerProfile.resume_section_toggles's docstring.
        """
        toggles = profile.resume_section_toggles
        return True if toggles is None else toggles.get(section_key, True)

    async def _gather(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> tuple[CareerProfile, ResumeData]:
        profile = await self._profiles.get_by_user_id(tenant_id, user_id, target_role_id)
        if profile is None:
            raise NotFoundError("Career profile not found.", code="CAREER_PROFILE_NOT_FOUND")

        user = await self._users.get_by_id(tenant_id, user_id)
        assert user is not None, "authenticated user must exist"

        role_label: str | None = None
        if profile.target_role_id is not None:
            role = await self._target_roles.get_by_id(tenant_id, profile.target_role_id)
            role_label = role.role_name if role else None

        experiences = await self._experiences.list_for_profile(tenant_id, profile.id)
        educations = await self._educations.list_for_profile(tenant_id, profile.id)
        certifications = await self._certifications.list_for_profile(tenant_id, profile.id)
        career_highlights = await self._career_highlights.list_for_profile(tenant_id, profile.id)
        key_achievements = await self._key_achievements.list_for_profile(tenant_id, profile.id)
        # Scoped by user_id, not career_profile_id — CareerGoal is shared
        # across the Master Profile and every Target Role Profile (see
        # CareerGoal's entity docstring), so it's fetched the same way
        # regardless of which profile this export is for.
        career_goals = await self._career_goals.list_for_user(tenant_id, user_id)
        recommendations = await self._peer_endorsements.list_for_profile(tenant_id, profile.id)

        # A whole section toggled off excludes every item in it,
        # regardless of each item's own toggle; otherwise only the
        # individually toggled-off items are dropped. The profile itself
        # is filtered into a resume-only view (core_competencies) rather
        # than mutated in place, since the *unfiltered* profile is still
        # what gets persisted (resume_docx_key/resume_pdf_key) below.
        resume_profile = replace(
            profile,
            core_competencies=(
                [c for c in profile.core_competencies if c.include_in_resume]
                if self._section_enabled(profile, "core_competencies")
                else []
            ),
        )

        data = ResumeData(
            profile=resume_profile,
            user=user,
            experiences=(
                [e for e in experiences if e.include_in_resume]
                if self._section_enabled(profile, "experience")
                else []
            ),
            educations=(
                [e for e in educations if e.include_in_resume]
                if self._section_enabled(profile, "education")
                else []
            ),
            certifications=(
                [c for c in certifications if c.include_in_resume]
                if self._section_enabled(profile, "certifications")
                else []
            ),
            career_highlights=(
                [h for h in career_highlights if h.include_in_resume]
                if self._section_enabled(profile, "career_highlights")
                else []
            ),
            key_achievements=(
                [a for a in key_achievements if a.include_in_resume]
                if self._section_enabled(profile, "key_achievements")
                else []
            ),
            career_goals=(
                [g for g in career_goals if g.include_in_resume]
                if self._section_enabled(profile, "career_goals")
                else []
            ),
            recommendations=(
                [p for p in recommendations if p.include_in_resume]
                if self._section_enabled(profile, "recommendations")
                else []
            ),
            role_label=role_label,
        )
        return profile, data

    async def generate(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        format: ResumeFormat,
    ) -> tuple[CareerProfile, str]:
        """Builds the requested format, uploads it (overwriting any
        previous file of the same format for this profile), updates the
        profile's resume_{format}_key/resume_generated_at, and returns
        (updated_profile, a fresh presigned download URL).
        """
        profile, data = await self._gather(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )

        content = build_resume_docx(data) if format == "docx" else build_resume_pdf(data)

        key = f"generated-resumes/{tenant_id}/{profile.id}/resume.{format}"
        await self._storage.upload_private(
            key=key, content=content, content_type=_CONTENT_TYPES[format]
        )

        if format == "docx":
            profile.resume_docx_key = key
        else:
            profile.resume_pdf_key = key
        profile.resume_generated_at = datetime.now(UTC)
        updated = await self._profiles.update(profile)

        filename = _resume_filename(
            display_name=data.user.display_name or data.user.email,
            role_label=data.role_label,
            format=format,
        )
        url = await self._storage.get_presigned_url(
            key=key, expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS, download_filename=filename
        )
        return updated, url

    async def get_download_urls(
        self, *, tenant_id: UUID, profile: CareerProfile
    ) -> ResumeDownloadUrls:
        """Fresh presigned URLs for whichever formats have already been
        generated for this profile (None for a format never generated)
        — used when building the GET /career-profile response, since a
        stored presigned URL would expire long before anyone re-fetches
        the profile page. Looks up the owning user/target role at most
        once regardless of how many formats exist, rather than once per
        format.
        """
        if profile.resume_docx_key is None and profile.resume_pdf_key is None:
            return ResumeDownloadUrls(docx_url=None, pdf_url=None)

        user = await self._users.get_by_id(tenant_id, profile.user_id)
        assert user is not None, "profile owner must exist"
        role_label: str | None = None
        if profile.target_role_id is not None:
            role = await self._target_roles.get_by_id(tenant_id, profile.target_role_id)
            role_label = role.role_name if role else None

        display_name = user.display_name or user.email
        docx_url = None
        if profile.resume_docx_key is not None:
            docx_url = await self._storage.get_presigned_url(
                key=profile.resume_docx_key,
                expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS,
                download_filename=_resume_filename(
                    display_name=display_name, role_label=role_label, format="docx"
                ),
            )
        pdf_url = None
        if profile.resume_pdf_key is not None:
            pdf_url = await self._storage.get_presigned_url(
                key=profile.resume_pdf_key,
                expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS,
                download_filename=_resume_filename(
                    display_name=display_name, role_label=role_label, format="pdf"
                ),
            )
        return ResumeDownloadUrls(docx_url=docx_url, pdf_url=pdf_url)
