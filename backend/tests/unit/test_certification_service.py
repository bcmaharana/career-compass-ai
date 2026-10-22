from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.career_profile.schemas import CertificationRequest
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.public_certification_service import PublicCertificationService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import Certification


class FakeCertificationRepository:
    def __init__(self, certification: Certification) -> None:
        self.certification = certification

    async def get_by_id(
        self, tenant_id: uuid.UUID, certification_id: uuid.UUID
    ) -> Certification | None:
        if self.certification.id != certification_id or self.certification.tenant_id != tenant_id:
            return None
        return self.certification

    async def update(self, certification: Certification) -> Certification:
        self.certification = certification
        return certification


class FakeCareerProfiles:
    def __init__(self, profile_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.profile = SimpleNamespace(id=profile_id, user_id=user_id)

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID):
        return self.profile if self.profile.id == profile_id else None


class FakeUsers:
    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID):
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
        download_filename=None,
        disposition="attachment",
    ) -> str:
        return f"https://storage.test/{key}"

    async def delete_private(self, *, key: str) -> None:
        self.deleted.append(key)


class FakeShareLinks:
    def __init__(self) -> None:
        self.link = None

    async def get_by_resource(self, resource_type: str, resource_id: uuid.UUID):
        if self.link and self.link.resource_id == resource_id:
            return self.link
        return None

    async def get_by_key(self, share_key: str):
        return self.link if self.link and self.link.share_key == share_key else None

    async def create(self, link):
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


def make_certification(tenant_id: uuid.UUID, profile_id: uuid.UUID) -> Certification:
    now = datetime.now(UTC)
    return Certification(
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


def test_certificate_external_links_require_http_or_https() -> None:
    valid = {
        "name": "Certificate",
        "issuing_organization": "Example Institute",
        "credential_url": "https://example.test/verify",
        "badge_url": "http://example.test/badge.png",
    }
    assert CertificationRequest(**valid).credential_url == valid["credential_url"]

    with pytest.raises(PydanticValidationError):
        CertificationRequest(**{**valid, "badge_url": "javascript:alert(1)"})


@pytest.mark.asyncio
async def test_non_expiring_certification_clears_expiration_date() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    certification = make_certification(tenant_id, profile_id)
    certification.expiration_date = date(2030, 1, 1)
    repository = FakeCertificationRepository(certification)
    service = CertificationService(
        repository,
        FakeCareerProfiles(profile_id, user_id),
        FakeShareLinks(),
        FakePrivateStorage(),
    )

    updated = await service.update(
        tenant_id=tenant_id,
        user_id=user_id,
        certification_id=certification.id,
        name=certification.name,
        issuing_organization=certification.issuing_organization,
        issue_date=certification.issue_date,
        expiration_date=certification.expiration_date,
        credential_id=certification.credential_id,
        credential_url=certification.credential_url,
        does_not_expire=True,
    )

    assert updated.does_not_expire is True
    assert updated.expiration_date is None


@pytest.mark.asyncio
async def test_upload_stores_valid_pdf_in_private_storage() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    certification = make_certification(tenant_id, profile_id)
    repository = FakeCertificationRepository(certification)
    storage = FakePrivateStorage()
    service = CertificationService(
        repository,
        FakeCareerProfiles(profile_id, user_id),
        FakeShareLinks(),
        storage,
    )

    updated = await service.upload_file(
        tenant_id=tenant_id,
        user_id=user_id,
        certification_id=certification.id,
        file_kind="certificate",
        filename="award.pdf",
        content=b"%PDF-1.7 sample",
    )

    assert updated.certificate_file_name == "award.pdf"
    assert updated.certificate_file_content_type == "application/pdf"
    assert updated.certificate_file_key == storage.uploaded[0][0]
    assert storage.uploaded[0][1:] == (b"%PDF-1.7 sample", "application/pdf")


@pytest.mark.asyncio
async def test_upload_rejects_invalid_file_content_and_other_users() -> None:
    tenant_id, user_id, other_user_id, profile_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    certification = make_certification(tenant_id, profile_id)
    storage = FakePrivateStorage()
    service = CertificationService(
        FakeCertificationRepository(certification),
        FakeCareerProfiles(profile_id, user_id),
        FakeShareLinks(),
        storage,
    )

    with pytest.raises(ValidationError):
        await service.upload_file(
            tenant_id=tenant_id,
            user_id=user_id,
            certification_id=certification.id,
            file_kind="certificate",
            filename="fake.pdf",
            content=b"not a PDF",
        )

    with pytest.raises(NotFoundError):
        await service.upload_file(
            tenant_id=tenant_id,
            user_id=other_user_id,
            certification_id=certification.id,
            file_kind="certificate",
            filename="award.pdf",
            content=b"%PDF-1.7 sample",
        )

    assert storage.uploaded == []


@pytest.mark.asyncio
async def test_share_link_is_created_and_revoked_for_one_certificate() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    certification = make_certification(tenant_id, profile_id)
    links = FakeShareLinks()
    service = CertificationService(
        FakeCertificationRepository(certification),
        FakeCareerProfiles(profile_id, user_id),
        links,
        FakePrivateStorage(),
    )

    share_key = await service.get_or_create_share_link(
        tenant_id=tenant_id, user_id=user_id, certification_id=certification.id
    )
    assert share_key == links.link.share_key
    assert len(share_key) >= 32

    await service.revoke_share_link(
        tenant_id=tenant_id, user_id=user_id, certification_id=certification.id
    )
    assert links.link is None


@pytest.mark.asyncio
async def test_public_certificate_resolves_only_through_its_share_key() -> None:
    tenant_id, user_id, profile_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    certification = make_certification(tenant_id, profile_id)
    certification.does_not_expire = True
    certification.certificate_file_key = "certificates/private/proof.pdf"
    certification.badge_image_key = "certificates/private/badge.png"
    links = FakeShareLinks()
    owner_service = CertificationService(
        FakeCertificationRepository(certification),
        FakeCareerProfiles(profile_id, user_id),
        links,
        FakePrivateStorage(),
    )
    share_key = await owner_service.get_or_create_share_link(
        tenant_id=tenant_id, user_id=user_id, certification_id=certification.id
    )

    tenant_context = FakeTenantContext()
    public_service = PublicCertificationService(
        links,
        tenant_context,
        FakeCertificationRepository(certification),
        FakeCareerProfiles(profile_id, user_id),
        FakeUsers(),
        FakePrivateStorage(),
    )
    view = await public_service.get_certificate(share_key)

    assert view is not None
    assert view.certification.does_not_expire is True
    assert view.owner_display_name == "Ada Lovelace"
    assert tenant_context.bound_tenants == [tenant_id]
    assert view.certificate_file_url == ("https://storage.test/certificates/private/proof.pdf")
    assert view.badge_image_url == "https://storage.test/certificates/private/badge.png"
    assert await public_service.get_certificate("unknown-key") is None
