"""Unit tests for DeleteAccountService."""

from __future__ import annotations

import uuid

import pytest

from app.application.identity.delete_account import DeleteAccountService
from app.core.exceptions import CareerCompassError
from app.domain.identity.account_deletion import TenantDeletionArtifacts


class FakeAccountDeletionRepository:
    def __init__(self, artifacts: TenantDeletionArtifacts) -> None:
        self.artifacts = artifacts
        self.deleted_tenant_ids: list[uuid.UUID] = []

    async def delete_tenant(self, tenant_id: uuid.UUID) -> TenantDeletionArtifacts:
        self.deleted_tenant_ids.append(tenant_id)
        return self.artifacts


class StorageError(CareerCompassError):
    code = "OBJECT_STORAGE_ERROR"


class FakeObjectStorage:
    def __init__(self, *, fail_photo_delete: bool = False, fail_resume_delete: bool = False) -> None:
        self.fail_photo_delete = fail_photo_delete
        self.fail_resume_delete = fail_resume_delete
        self.deleted_photo_keys: list[str] = []
        self.deleted_resume_keys: list[str] = []

    async def delete(self, *, key: str) -> None:
        if self.fail_photo_delete:
            raise StorageError("simulated photo delete failure")
        self.deleted_photo_keys.append(key)

    async def delete_private(self, *, key: str) -> None:
        if self.fail_resume_delete:
            raise StorageError("simulated resume delete failure")
        self.deleted_resume_keys.append(key)


@pytest.mark.unit
class TestDeleteAccount:
    async def test_deletes_the_tenant_and_cleans_up_storage(self) -> None:
        tenant_id = uuid.uuid4()
        profile_id = uuid.uuid4()
        page_id = uuid.uuid4()
        block_id = uuid.uuid4()
        artifacts = TenantDeletionArtifacts(
            resume_file_keys=["resumes/t/u/r1.pdf"],
            profile_photos=[(profile_id, f"https://cdn.example.com/profile-photos/{tenant_id}/{profile_id}.jpg?v=1")],
            interview_topic_image_keys=["interview-topics/t/topic1.jpg"],
            tailored_resume_file_keys=["tailored-resumes/t/s1/resume.docx"],
            showcase_block_image_urls=[
                f"https://cdn.example.com/showcase-pages/{tenant_id}/{page_id}/{block_id}.jpg?v=1"
            ],
            showcase_resume_file_keys=[f"showcase-resumes/{tenant_id}/{page_id}/resume.pdf"],
        )
        repo = FakeAccountDeletionRepository(artifacts)
        storage = FakeObjectStorage()
        service = DeleteAccountService(
            account_deletion=repo, photo_storage=storage, resume_storage=storage
        )

        await service.execute(tenant_id=tenant_id)

        assert repo.deleted_tenant_ids == [tenant_id]
        assert storage.deleted_resume_keys == [
            "resumes/t/u/r1.pdf",
            "interview-topics/t/topic1.jpg",
            "tailored-resumes/t/s1/resume.docx",
            f"showcase-resumes/{tenant_id}/{page_id}/resume.pdf",
        ]
        assert storage.deleted_photo_keys == [
            f"profile-photos/{tenant_id}/{profile_id}.jpg",
            f"showcase-pages/{tenant_id}/{page_id}/{block_id}.jpg",
        ]

    async def test_storage_failure_does_not_raise(self) -> None:
        tenant_id = uuid.uuid4()
        profile_id = uuid.uuid4()
        artifacts = TenantDeletionArtifacts(
            resume_file_keys=["resumes/t/u/r1.pdf"],
            profile_photos=[(profile_id, f"https://cdn.example.com/profile-photos/{tenant_id}/{profile_id}.jpg")],
            interview_topic_image_keys=["interview-topics/t/topic1.jpg"],
            tailored_resume_file_keys=["tailored-resumes/t/s1/resume.pdf"],
            showcase_block_image_urls=[],
            showcase_resume_file_keys=["showcase-resumes/t/p1/resume.pdf"],
        )
        repo = FakeAccountDeletionRepository(artifacts)
        storage = FakeObjectStorage(fail_photo_delete=True, fail_resume_delete=True)
        service = DeleteAccountService(
            account_deletion=repo, photo_storage=storage, resume_storage=storage
        )

        # DB deletion already happened (repo.delete_tenant was called) —
        # storage cleanup is best-effort and must not raise, matching
        # CareerProfileService.delete_photo's existing convention.
        await service.execute(tenant_id=tenant_id)

        assert repo.deleted_tenant_ids == [tenant_id]

    async def test_no_photos_or_resumes_is_a_no_op_for_storage(self) -> None:
        tenant_id = uuid.uuid4()
        artifacts = TenantDeletionArtifacts(
            resume_file_keys=[],
            profile_photos=[],
            interview_topic_image_keys=[],
            tailored_resume_file_keys=[],
            showcase_block_image_urls=[],
            showcase_resume_file_keys=[],
        )
        repo = FakeAccountDeletionRepository(artifacts)
        storage = FakeObjectStorage()
        service = DeleteAccountService(
            account_deletion=repo, photo_storage=storage, resume_storage=storage
        )

        await service.execute(tenant_id=tenant_id)

        assert storage.deleted_photo_keys == []
        assert storage.deleted_resume_keys == []
