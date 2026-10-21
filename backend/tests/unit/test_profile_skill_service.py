from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.career_profile.schemas import ProfileSkillRequest
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.profile_skill_service import ProfileSkillService
from app.application.career_profile.public_profile_skill_service import PublicProfileSkillService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import ProfileSkill
from app.domain.career_profile.repositories import CareerProfileRepository, ProfileSkillRepository
from app.domain.identity.repositories import UserRepository
from app.domain.showcase_page.entities import PublicShareLink


class FakeProfileSkillRepository:
    def __init__(self, profile_skill: ProfileSkill) -> None:
        self.profile_skill = profile_skill

    async def get_by_id(self, tenant_id: uuid.UUID, skill_id: uuid.UUID) -> ProfileSkill | None:
        if self.profile_skill.id != skill_id or self.profile_skill.tenant_id != tenant_id:
            return None
        return self.profile_skill

    async def update(self, profile_skill: ProfileSkill) -> ProfileSkill:
        self.profile_skill = profile_skill
        return profile_skill


class FakeCareerProfiles:
    def __init__(self, profile_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.profile = SimpleNamespace(id=profile_id, user_id=user_id)

    async def get_by_id(
        self, tenant_id: uuid.UUID, profile_id: uuid.UUID
    ) -> SimpleNamespace | None:
        return self.profile if self.profile.id == profile_id else None


class FakeUsers:
    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(display_name="Ada Lovelace")


class FakePrivateStorage:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes, str]] = []
        self.deleted: list[str] = []

    async def upload_private(self, *, key: str, content: bytes, content_type: str) -> None:
        self.uploaded.append((key, content, content_type))

    async def get_presigned_url(
        self,
        *,
        key: str,
        expires_in_seconds: int = 300,
        download_filename: str | None = None,
        disposition: str = "attachment",
    ) -> str:
        return f"https://storage.test/{key}"

    async def delete_private(self, *, key: str) -> None:
        self.deleted.append(key)


class FakeShareLinks:
    def __init__(self) -> None:
        self.link: PublicShareLink | None = None

    async def get_by_resource(
        self, resource_type: str, resource_id: uuid.UUID
    ) -> PublicShareLink | None:
        if self.link and self.link.resource_id == resource_id:
            return self.link
        return None

    async def get_by_key(self, share_key: str) -> PublicShareLink | None:
        return self.link if self.link and self.link.share_key == share_key else None

    async def create(self, link: PublicShareLink) -> PublicShareLink:
        self.link = link
        return link

    async def delete_by_resource(self, resource_type: str, resource_id: uuid.UUID) -> None:
        if self.link and self.link.resource_id == resource_id:
            self.link = None


class FakeTenantContext:
    def __init__(self) -> None:
        self.bound_tenants: list[uuid.UUID] = []

    async def bind(self, tenant_id: uuid.UUID) -> None:
        self.bound_tenants.append(tenant_id)


def make_profile_skill(tenant_id: uuid.UUID, profile_id: uuid.UUID) -> ProfileSkill:
    now = datetime.now(UTC)
    return ProfileSkill(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        career_profile_id=profile_id,
        name="Cloud Architect",
        issuing_organization="Example Institute",
        issue_date=date(2025, 1, 1),
        expiration_date=None,
        credential_id=None,
        credential_url=None,
        display_order=0,
        created_at=now,
        updated_at=now,
    )


def test_skill_external_links_require_http_or_https() -> None:
    valid = {
        "name": "Cloud Architecture",
        "issuing_organization": "Example Institute",
        "credential_url": "https://example.test/verify",
        "badge_url": "http://example.test/badge.png",
    }
    assert ProfileSkillRequest.model_validate(valid).credential_url == valid["credential_url"]

    with pytest.raises(PydanticValidationError):
        ProfileSkillRequest.model_validate({**valid, "badge_url": "javascript:alert(1)"})


@pytest.mark.asyncio
async def test_upload_stores_valid_pdf_in_private_storage() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    profile_skill = make_profile_skill(tenant_id, profile_id)
    repository = FakeProfileSkillRepository(profile_skill)
    storage = FakePrivateStorage()
    service = ProfileSkillService(
        cast(ProfileSkillRepository, repository),
        cast(CareerProfileService, FakeCareerProfiles(profile_id, user_id)),
        FakeShareLinks(),
        storage,
    )

    updated = await service.upload_file(
        tenant_id=tenant_id,
        user_id=user_id,
        skill_id=profile_skill.id,
        file_kind="skill",
        filename="award.pdf",
        content=b"%PDF-1.7 sample",
    )

    assert updated.skill_file_name == "award.pdf"
    assert updated.skill_file_content_type == "application/pdf"
    assert updated.skill_file_key == storage.uploaded[0][0]
    assert storage.uploaded[0][1:] == (b"%PDF-1.7 sample", "application/pdf")


@pytest.mark.asyncio
async def test_upload_rejects_invalid_file_content_and_other_users() -> None:
    tenant_id, user_id, other_user_id, profile_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    profile_skill = make_profile_skill(tenant_id, profile_id)
    storage = FakePrivateStorage()
    service = ProfileSkillService(
        cast(ProfileSkillRepository, FakeProfileSkillRepository(profile_skill)),
        cast(CareerProfileService, FakeCareerProfiles(profile_id, user_id)),
        FakeShareLinks(),
        storage,
    )

    with pytest.raises(ValidationError):
        await service.upload_file(
            tenant_id=tenant_id,
            user_id=user_id,
            skill_id=profile_skill.id,
            file_kind="skill",
            filename="fake.pdf",
            content=b"not a PDF",
        )

    with pytest.raises(NotFoundError):
        await service.upload_file(
            tenant_id=tenant_id,
            user_id=other_user_id,
            skill_id=profile_skill.id,
            file_kind="skill",
            filename="award.pdf",
            content=b"%PDF-1.7 sample",
        )

    assert storage.uploaded == []


@pytest.mark.asyncio
async def test_share_link_is_created_and_revoked_for_one_skill() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    profile_skill = make_profile_skill(tenant_id, profile_id)
    links = FakeShareLinks()
    service = ProfileSkillService(
        cast(ProfileSkillRepository, FakeProfileSkillRepository(profile_skill)),
        cast(CareerProfileService, FakeCareerProfiles(profile_id, user_id)),
        links,
        FakePrivateStorage(),
    )

    share_key = await service.get_or_create_share_link(
        tenant_id=tenant_id, user_id=user_id, skill_id=profile_skill.id
    )
    assert links.link is not None
    assert share_key == links.link.share_key
    assert len(share_key) >= 32

    await service.revoke_share_link(tenant_id=tenant_id, user_id=user_id, skill_id=profile_skill.id)
    assert links.link is None


@pytest.mark.asyncio
async def test_public_skill_resolves_only_through_its_share_key() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    profile_skill = make_profile_skill(tenant_id, profile_id)
    profile_skill.skill_file_key = "career-profile-skills/private/proof.pdf"
    profile_skill.badge_image_key = "career-profile-skills/private/badge.png"
    links = FakeShareLinks()
    owner_service = ProfileSkillService(
        cast(ProfileSkillRepository, FakeProfileSkillRepository(profile_skill)),
        cast(CareerProfileService, FakeCareerProfiles(profile_id, user_id)),
        links,
        FakePrivateStorage(),
    )
    share_key = await owner_service.get_or_create_share_link(
        tenant_id=tenant_id, user_id=user_id, skill_id=profile_skill.id
    )

    tenant_context = FakeTenantContext()
    public_service = PublicProfileSkillService(
        links,
        tenant_context,
        cast(ProfileSkillRepository, FakeProfileSkillRepository(profile_skill)),
        cast(CareerProfileRepository, FakeCareerProfiles(profile_id, user_id)),
        cast(UserRepository, FakeUsers()),
        FakePrivateStorage(),
    )
    view = await public_service.get_skill(share_key)

    assert view is not None
    assert view.owner_display_name == "Ada Lovelace"
    assert tenant_context.bound_tenants == [tenant_id]
    assert view.skill_file_url == "https://storage.test/career-profile-skills/private/proof.pdf"
    assert view.badge_image_url == "https://storage.test/career-profile-skills/private/badge.png"
    assert await public_service.get_skill("unknown-key") is None
