"""Unit tests for ResumeExportService.

Fake in-memory repositories satisfying the Protocol interfaces in
app/domain/career_profile/repositories.py / app/domain/identity/repositories.py
— no database, no real object storage. FakeStorage records uploads
instead of touching MinIO/S3, matching FakeObjectStorageRepository's
role in test_career_profile_service.py. Document *content* (the actual
docx/pdf bytes) is covered by resume_docx_builder.py/resume_pdf_builder.py
being called directly here (real builders, not faked) — these tests
focus on ResumeExportService's own orchestration: gathering the right
data, building the right storage key, and persisting the right fields.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.career_profile.resume_export_service import ResumeExportService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import CareerProfile, TargetRole
from app.domain.identity.entities import User


class FakeCareerProfileRepository:
    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None = None
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.user_id == user_id
                and profile.target_role_id == target_role_id
            ):
                return replace(profile)
        return None

    async def get_by_id(
        self, tenant_id: uuid.UUID, profile_id: uuid.UUID
    ) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeEmptyChildRepository:
    """Stands in for Experience/Education/Certification/CareerHighlight/
    KeyAchievement — ResumeExportService only ever calls list_for_profile
    on these (via the narrow _ProfileScopedReader Protocol, not the full
    per-domain repository Protocols), and an empty profile (no child
    entities) is enough to exercise the orchestration logic under test
    here — the builders' handling of real child data was already
    exercised directly via the manual smoke test that produced the
    sample .docx/.pdf sent for layout review.
    """

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Any]:
        return []

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Any]:
        # CareerGoal is user_id-scoped, not career_profile_id-scoped (see
        # CareerGoal's entity docstring) — this method lets the same fake
        # stand in for it too, alongside the profile-scoped entities.
        return []


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.roles: dict[uuid.UUID, TargetRole] = {}

    async def get_by_id(
        self, tenant_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> TargetRole | None:
        role = self.roles.get(target_role_id)
        return replace(role) if role and role.tenant_id == tenant_id else None


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user and user.tenant_id == tenant_id else None


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    async def upload_private(self, *, key: str, content: bytes, content_type: str) -> None:
        self.uploaded[key] = content

    async def get_presigned_url(
        self,
        *,
        key: str,
        expires_in_seconds: int = 300,
        download_filename: str | None = None,
    ) -> str:
        suffix = f"?filename={download_filename}" if download_filename else ""
        return f"https://example.test/{key}{suffix}"

    async def delete_private(self, *, key: str) -> None:
        self.uploaded.pop(key, None)


def _make_profile(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None = None
) -> CareerProfile:
    now = datetime.now(UTC)
    return CareerProfile(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        current_version=1,
        headline="Senior Engineer",
        summary="Builds things.",
        career_readiness_score=None,
        photo_url=None,
        core_competencies=[],
        created_at=now,
        updated_at=now,
        target_role_id=target_role_id,
    )


def _make_user(*, tenant_id: uuid.UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def _build() -> tuple[
    ResumeExportService, FakeCareerProfileRepository, FakeUserRepository, FakeStorage
]:
    profiles = FakeCareerProfileRepository()
    users = FakeUserRepository()
    storage = FakeStorage()
    service = ResumeExportService(
        profiles=profiles,
        experiences=FakeEmptyChildRepository(),
        educations=FakeEmptyChildRepository(),
        certifications=FakeEmptyChildRepository(),
        career_highlights=FakeEmptyChildRepository(),
        key_achievements=FakeEmptyChildRepository(),
        career_goals=FakeEmptyChildRepository(),
        peer_endorsements=FakeEmptyChildRepository(),
        target_roles=FakeTargetRoleRepository(),
        users=users,
        storage=storage,
    )
    return service, profiles, users, storage


@pytest.mark.unit
class TestGenerate:
    async def test_generate_docx_uploads_and_persists_key(self) -> None:
        service, profiles, users, storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        profile = _make_profile(tenant_id=tenant_id, user_id=user.id)
        await profiles.create(profile)

        updated, url = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="docx"
        )

        assert updated.resume_docx_key == f"generated-resumes/{tenant_id}/{profile.id}/resume.docx"
        assert updated.resume_pdf_key is None
        assert updated.resume_generated_at is not None
        assert updated.resume_docx_key in storage.uploaded
        assert storage.uploaded[updated.resume_docx_key].startswith(b"PK")  # docx is a zip
        assert url.endswith(".docx")

    async def test_generate_pdf_does_not_clobber_an_existing_docx_key(self) -> None:
        service, profiles, users, _storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        profile = _make_profile(tenant_id=tenant_id, user_id=user.id)
        await profiles.create(profile)

        await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="docx"
        )
        updated, _url = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="pdf"
        )

        assert updated.resume_docx_key is not None
        assert updated.resume_pdf_key is not None

    async def test_regenerating_the_same_format_overwrites_not_accumulates(self) -> None:
        service, profiles, users, storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        profile = _make_profile(tenant_id=tenant_id, user_id=user.id)
        await profiles.create(profile)

        first, _ = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="docx"
        )
        second, _ = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="docx"
        )

        assert first.resume_docx_key == second.resume_docx_key
        # Only one object at that key — a real overwrite, not two.
        assert len(storage.uploaded) == 1

    async def test_target_role_profile_generates_independently_of_master(self) -> None:
        service, profiles, users, _storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        master = _make_profile(tenant_id=tenant_id, user_id=user.id)
        await profiles.create(master)

        role_id = uuid.uuid4()
        role_profile = _make_profile(tenant_id=tenant_id, user_id=user.id, target_role_id=role_id)
        await profiles.create(role_profile)

        await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="docx"
        )
        role_updated, _url = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=role_id, format="docx"
        )

        master_after = await profiles.get_by_user_id(tenant_id, user.id, None)
        assert master_after is not None
        assert master_after.resume_docx_key != role_updated.resume_docx_key

    async def test_raises_not_found_for_a_profile_that_does_not_exist(self) -> None:
        service, _profiles, _users, _storage = _build()

        with pytest.raises(NotFoundError):
            await service.generate(
                tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), target_role_id=None, format="docx"
            )


@pytest.mark.unit
class TestGetDownloadUrls:
    async def test_returns_none_for_both_when_never_generated(self) -> None:
        service, profiles, users, _storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        profile = await profiles.create(_make_profile(tenant_id=tenant_id, user_id=user.id))

        urls = await service.get_download_urls(tenant_id=tenant_id, profile=profile)

        assert urls.docx_url is None
        assert urls.pdf_url is None

    async def test_returns_a_fresh_url_for_a_generated_format_only(self) -> None:
        service, profiles, users, _storage = _build()
        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        users.users[user.id] = user
        await profiles.create(_make_profile(tenant_id=tenant_id, user_id=user.id))

        updated, _url = await service.generate(
            tenant_id=tenant_id, user_id=user.id, target_role_id=None, format="pdf"
        )

        urls = await service.get_download_urls(tenant_id=tenant_id, profile=updated)

        assert urls.docx_url is None
        assert urls.pdf_url is not None
        assert urls.pdf_url.startswith("https://example.test/")
