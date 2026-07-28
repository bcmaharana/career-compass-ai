"""Object storage abstraction.

Application services depend only on this Protocol — the concrete
implementation (S3/MinIO-compatible, see
app/adapters/storage/s3_object_storage.py) is swappable without any
calling code changing, same pattern as IdentityProviderInterface and
LLMProviderInterface.
"""

from __future__ import annotations

from typing import Protocol


class ObjectStorageRepository(Protocol):
    async def upload(
        self, *, key: str, content: bytes, content_type: str
    ) -> str:
        """Upload an object and return its publicly-servable URL.

        Raises app.core.exceptions.CareerCompassError (or a subclass) on
        failure — provider-specific exceptions must be translated at the
        adapter boundary.
        """
        ...

    async def delete(self, *, key: str) -> None:
        """Delete an object. Must not raise if the key doesn't exist —
        deletion is idempotent from the caller's perspective."""
        ...
