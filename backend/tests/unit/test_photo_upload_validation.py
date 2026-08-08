"""Unit tests for CareerProfileService.upload_photo's validation logic.

Uses a fake ObjectStorageRepository — the real S3-compatible adapter
(app/adapters/storage/s3_object_storage.py) requires a running
MinIO/S3-compatible endpoint (see infra/docker-compose.yml), which isn't
available in every environment these unit tests run in. Validation logic
(content type, size limits) runs *before* any storage call, so it's
fully testable without one; the successful-upload path is exercised here
against the fake to confirm the service wires everything together
correctly, while true end-to-end verification against real MinIO belongs
in a manual/integration check against a running docker-compose stack.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import replace

import pytest

from app.application.career_profile.career_profile_service import (
    MAX_PHOTO_SIZE_BYTES,
    CareerProfileService,
)
from app.core.exceptions import ValidationError
from app.domain.career_profile.entities import CareerProfile, CareerProfileVersion


class FakeCareerProfileRepository:
    """See tests/unit/test_career_profile_service.py for why fetches
    return a copy rather than the live object reference."""

    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        target_role_id: uuid.UUID | None = None,
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.user_id == user_id
                and profile.target_role_id == target_role_id
            ):
                return replace(profile)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeCareerProfileVersionRepository:
    def __init__(self) -> None:
        self.versions: list[CareerProfileVersion] = []

    async def create(self, version: CareerProfileVersion) -> CareerProfileVersion:
        self.versions.append(version)
        return version

    async def list_for_profile(
        self, career_profile_id: uuid.UUID, *, limit: int = 50
    ) -> list[CareerProfileVersion]:
        return [v for v in self.versions if v.career_profile_id == career_profile_id][:limit]


class FakeObjectStorageRepository:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}
        self.deleted_keys: list[str] = []

    async def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        self.uploaded[key] = content
        return f"https://fake-storage.test/{key}"

    async def delete(self, *, key: str) -> None:
        self.deleted_keys.append(key)


@pytest.fixture
def service_with_storage():
    profiles = FakeCareerProfileRepository()
    versions = FakeCareerProfileVersionRepository()
    storage = FakeObjectStorageRepository()
    return CareerProfileService(profiles, versions, storage), storage


@pytest.mark.unit
class TestPhotoUploadValidation:
    async def test_rejects_unsupported_content_type(self, service_with_storage) -> None:
        svc, _ = service_with_storage

        with pytest.raises(ValidationError) as exc_info:
            await svc.upload_photo(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                content=b"not-really-an-image",
                content_type="application/pdf",
            )

        assert exc_info.value.code == "UNSUPPORTED_PHOTO_TYPE"

    async def test_rejects_oversized_content(self, service_with_storage) -> None:
        svc, _ = service_with_storage
        oversized_content = b"x" * (MAX_PHOTO_SIZE_BYTES + 1)

        with pytest.raises(ValidationError) as exc_info:
            await svc.upload_photo(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                content=oversized_content,
                content_type="image/png",
            )

        assert exc_info.value.code == "PHOTO_TOO_LARGE"

    async def test_accepts_valid_photo_and_updates_profile(self, service_with_storage) -> None:
        svc, storage = service_with_storage
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        profile = await svc.upload_photo(
            tenant_id=tenant_id,
            user_id=user_id,
            content=b"fake-jpeg-bytes",
            content_type="image/jpeg",
        )

        assert profile.photo_url is not None
        assert profile.photo_url.startswith("https://fake-storage.test/")
        assert len(storage.uploaded) == 1

    async def test_upload_bumps_profile_version(self, service_with_storage) -> None:
        svc, _ = service_with_storage
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        profile = await svc.upload_photo(
            tenant_id=tenant_id, user_id=user_id, content=b"data", content_type="image/png"
        )

        assert profile.current_version == 2

    async def test_reuploading_produces_a_different_url(self, service_with_storage) -> None:
        """The storage KEY stays stable across re-uploads (one file per
        profile, so old photos don't pile up in storage), but a stable
        URL means a browser's image cache never sees a reason to
        re-fetch it, even though the underlying file changed. Confirms
        the cache-busting query param actually differs between two
        uploads to the same profile.
        """
        svc, storage = service_with_storage
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await svc.upload_photo(
            tenant_id=tenant_id, user_id=user_id, content=b"version-one", content_type="image/png"
        )
        # Ensure the two uploads don't land in the same integer second,
        # since the cache-buster is a unix timestamp.
        time.sleep(1.1)
        second = await svc.upload_photo(
            tenant_id=tenant_id, user_id=user_id, content=b"version-two", content_type="image/png"
        )

        assert first.photo_url != second.photo_url
        # Same underlying storage key both times (URL differs only by
        # the cache-busting query string appended after upload) — and
        # since it's the same key, the second upload correctly
        # overwrites the first in storage rather than leaving two files
        # behind.
        base_first = first.photo_url.split("?")[0]
        base_second = second.photo_url.split("?")[0]
        assert base_first == base_second
        assert len(storage.uploaded) == 1
        assert list(storage.uploaded.values())[0] == b"version-two"
