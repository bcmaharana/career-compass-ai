"""Career profile application service.

Handles the "one profile per user, created lazily on first access"
pattern, and the versioning behavior from the Phase 0 design package: any
update to tracked fields (headline, summary, core_competencies) snapshots
the prior state to CareerProfileVersion before applying the change, and
bumps current_version. Profile picture upload is versioned too (the old
photo_url is captured in the snapshot the same way), but goes through a
separate method since it's a distinct action (file upload vs. form
fields) with its own failure modes (storage errors).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from app.core.exceptions import CareerCompassError, ValidationError
from app.domain.career_profile.entities import CareerProfile, CareerProfileVersion, CoreCompetency
from app.domain.career_profile.repositories import (
    CareerProfileRepository,
    CareerProfileVersionRepository,
)
from app.domain.career_profile.storage import ObjectStorageRepository

MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_PHOTO_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def photo_key_from_url(*, tenant_id: UUID, profile_id: UUID, photo_url: str) -> str | None:
    """Reconstructs the storage key from a stored photo_url.

    The key itself (`profile-photos/{tenant_id}/{profile_id}.{ext}`) is
    never persisted as its own field — only the full public URL (plus a
    cache-busting `?v=` query param, see upload_photo) is. The extension
    is the only part of the key not otherwise derivable, so it's parsed
    back out of the URL path here.

    Intentionally public (not `_`-prefixed) — also reused by
    app/application/identity/delete_account.py for account-deletion S3
    cleanup, not just this module's own delete_photo().
    """
    path = urlsplit(photo_url).path
    if "." not in path:
        return None
    extension = path.rsplit(".", 1)[-1]
    return f"profile-photos/{tenant_id}/{profile_id}.{extension}"


class CareerProfileService:
    def __init__(
        self,
        profiles: CareerProfileRepository,
        versions: CareerProfileVersionRepository,
        storage: ObjectStorageRepository | None = None,
    ) -> None:
        self._profiles = profiles
        self._versions = versions
        # Optional: only required by upload_photo/delete_photo. Kept
        # optional here (rather than a hard constructor requirement) so
        # every other CareerProfileService use doesn't need a storage
        # adapter wired in just to, say, update a headline.
        self._storage = storage

    async def get_by_id(self, *, tenant_id: UUID, profile_id: UUID) -> CareerProfile | None:
        """Used by every child service's `_get_owned_or_raise` to resolve
        ownership from an item's own `career_profile_id`, rather than
        re-resolving "the" profile via `get_or_create` — the latter
        always means Master unless a `target_role_id` happens to be
        passed, so it would incorrectly 404 any edit/delete/move on an
        item that actually lives on a Target Role Profile.
        """
        return await self._profiles.get_by_id(tenant_id, profile_id)

    async def get_or_create(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None = None
    ) -> CareerProfile:
        """target_role_id=None resolves the Master Profile (unchanged
        default — every existing caller that hasn't been updated to pass
        a scope keeps working exactly as before). A real id resolves (or
        lazily creates) that Target Role Profile instead — a fully
        independent row, not a filtered view of Master.
        """
        existing = await self._profiles.get_by_user_id(tenant_id, user_id, target_role_id)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        return await self._profiles.create(
            CareerProfile(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                current_version=1,
                headline=None,
                summary=None,
                career_readiness_score=None,
                photo_url=None,
                core_competencies=[],
                section_order=None,
                target_role_id=target_role_id,
                created_at=now,
                updated_at=now,
            )
        )

    async def _snapshot_and_bump(self, profile: CareerProfile, *, change_reason: str) -> None:
        """Shared by every update path: capture the profile's state
        *before* the caller mutates it, then bump current_version. The
        caller is responsible for actually changing fields on `profile`
        after calling this and before persisting it.
        """
        await self._versions.create(
            CareerProfileVersion(
                id=uuid.uuid4(),
                career_profile_id=profile.id,
                version_number=profile.current_version,
                snapshot={
                    "headline": profile.headline,
                    "summary": profile.summary,
                    "career_readiness_score": profile.career_readiness_score,
                    "photo_url": profile.photo_url,
                    "core_competencies": [
                        {"name": c.name, "category": c.category}
                        for c in profile.core_competencies
                    ],
                },
                change_reason=change_reason,
                created_at=datetime.now(UTC),
            )
        )
        profile.current_version += 1

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        headline: str | None,
        summary: str | None,
        core_competencies: list[CoreCompetency] | None = None,
        section_order: list[str] | None = None,
        target_role_id: UUID | None = None,
    ) -> CareerProfile:
        profile = await self.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        await self._snapshot_and_bump(profile, change_reason="profile_updated")

        profile.headline = headline
        profile.summary = summary
        if core_competencies is not None:
            profile.core_competencies = core_competencies
        if section_order is not None:
            profile.section_order = section_order
        return await self._profiles.update(profile)

    async def upload_photo(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        content: bytes,
        content_type: str,
    ) -> CareerProfile:
        if content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported image type '{content_type}'. Allowed: "
                f"{sorted(ALLOWED_PHOTO_CONTENT_TYPES)}",
                code="UNSUPPORTED_PHOTO_TYPE",
            )
        if len(content) > MAX_PHOTO_SIZE_BYTES:
            raise ValidationError(
                f"Photo exceeds the {MAX_PHOTO_SIZE_BYTES // (1024 * 1024)}MB limit.",
                code="PHOTO_TOO_LARGE",
            )
        assert self._storage is not None, "upload_photo requires a storage adapter"

        profile = await self.get_or_create(tenant_id=tenant_id, user_id=user_id)

        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
        key = f"profile-photos/{tenant_id}/{profile.id}.{extension}"
        photo_url = await self._storage.upload(key=key, content=content, content_type=content_type)

        # Cache-busting query param: the storage KEY is deliberately
        # stable across re-uploads (one file per profile, not one per
        # upload — otherwise old photos would accumulate in storage
        # forever). But a stable key means a stable URL, and a stable
        # URL means the browser's image cache has no reason to ever
        # re-fetch it — the new file was uploaded correctly, but the
        # <img> tag kept showing whatever it already had cached for that
        # exact URL. Appending the upload time forces every re-upload to
        # produce a distinct URL, which is what actually gets the
        # browser to load the new image.
        photo_url = f"{photo_url}?v={int(datetime.now(UTC).timestamp())}"

        await self._snapshot_and_bump(profile, change_reason="photo_updated")
        profile.photo_url = photo_url
        return await self._profiles.update(profile)

    async def delete_photo(self, *, tenant_id: UUID, user_id: UUID) -> CareerProfile:
        profile = await self.get_or_create(tenant_id=tenant_id, user_id=user_id)
        if profile.photo_url is not None and self._storage is not None:
            key = photo_key_from_url(
                tenant_id=tenant_id, profile_id=profile.id, photo_url=profile.photo_url
            )
            if key is not None:
                try:
                    await self._storage.delete(key=key)
                except CareerCompassError:
                    # Best-effort: the DB field is the source of truth for
                    # "does this profile have a photo," not the object's
                    # actual presence in the bucket — a storage-side failure
                    # here shouldn't block the user from clearing their
                    # profile. Worst case, an orphaned object is left behind.
                    pass

        await self._snapshot_and_bump(profile, change_reason="photo_removed")
        profile.photo_url = None
        return await self._profiles.update(profile)
