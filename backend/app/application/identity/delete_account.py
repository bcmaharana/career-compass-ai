"""Real, permanent "delete my account" — hard-deletes the whole tenant.

Scope note: this app has no multi-user-org/invite feature yet, so every
tenant today has exactly one user — "delete my account" and "delete my
tenant" are the same operation for now. Revisit if/when multi-user
orgs ship.

The actual multi-table delete (in dependency order, since no FK in
this schema has ON DELETE CASCADE — confirmed live, not assumed) lives
in app/adapters/db/account_deletion.py; this service only orchestrates
it plus the object-storage cleanup that has to happen alongside it.
"""

from __future__ import annotations

from uuid import UUID

from app.application.career_profile.career_profile_service import photo_key_from_url
from app.core.exceptions import CareerCompassError
from app.core.logging import get_logger
from app.domain.career_profile.storage import ObjectStorageRepository
from app.domain.identity.account_deletion import AccountDeletionRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository

logger = get_logger(__name__)


class DeleteAccountService:
    def __init__(
        self,
        account_deletion: AccountDeletionRepository,
        photo_storage: ObjectStorageRepository,
        resume_storage: PrivateObjectStorageRepository,
    ) -> None:
        self._account_deletion = account_deletion
        self._photo_storage = photo_storage
        self._resume_storage = resume_storage

    async def execute(self, *, tenant_id: UUID) -> None:
        artifacts = await self._account_deletion.delete_tenant(tenant_id)

        # Best-effort, same convention as CareerProfileService.delete_photo
        # — the DB row is already gone regardless of whether this
        # succeeds; an orphaned object is an acceptable worst case.
        for profile_id, photo_url in artifacts.profile_photos:
            key = photo_key_from_url(
                tenant_id=tenant_id, profile_id=profile_id, photo_url=photo_url
            )
            if key is None:
                continue
            try:
                await self._photo_storage.delete(key=key)
            except CareerCompassError:
                logger.warning("account_deletion_photo_cleanup_failed", key=key)

        for file_key in artifacts.resume_file_keys:
            try:
                await self._resume_storage.delete_private(key=file_key)
            except CareerCompassError:
                logger.warning("account_deletion_resume_cleanup_failed", key=file_key)
