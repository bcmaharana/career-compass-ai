"""Private object storage abstraction for resume files.

Deliberately separate from app.domain.career_profile.storage's
ObjectStorageRepository — that port's upload() returns a publicly
servable URL, which is correct for profile photos but wrong for
resumes, which carry real PII. The concrete adapter
(S3ObjectStorageRepository, app/adapters/storage/s3_object_storage.py)
satisfies both Protocols structurally against two separate buckets, one
public-read and one private.
"""

from __future__ import annotations

from typing import Protocol


class PrivateObjectStorageRepository(Protocol):
    async def upload_private(self, *, key: str, content: bytes, content_type: str) -> None:
        """Upload an object to a private bucket. Unlike ObjectStorageRepository.upload(),
        there is no publicly-servable URL to return.

        Raises app.core.exceptions.CareerCompassError (or a subclass) on
        failure — provider-specific exceptions must be translated at the
        adapter boundary.
        """
        ...

    async def get_presigned_url(
        self,
        *,
        key: str,
        expires_in_seconds: int = 300,
        download_filename: str | None = None,
    ) -> str:
        """Return a time-limited URL for retrieving a private object.

        download_filename, when given, makes opening the URL download
        with that name (via ResponseContentDisposition) instead of the
        raw storage key — used by ResumeExportService
        (app/application/career_profile/) so a link can carry a
        human-readable filename computed fresh from current profile
        data, without needing to re-upload just to change it.
        """
        ...

    async def delete_private(self, *, key: str) -> None:
        """Delete a private object. Must not raise if the key doesn't
        exist — deletion is idempotent from the caller's perspective."""
        ...
