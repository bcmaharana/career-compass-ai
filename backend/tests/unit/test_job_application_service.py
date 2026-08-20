"""Unit tests for JobApplicationService — fake repositories, no
database. Mirrors tests/unit/test_learning_item_service.py's
fake-repository pattern.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.job_application_tracking.job_application_service import (
    JobApplicationService,
)
from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import JobApplication, RecruiterContact

pytestmark = pytest.mark.unit


class FakeJobApplicationRepository:
    def __init__(self) -> None:
        self.applications: dict[uuid.UUID, JobApplication] = {}

    async def create(self, application: JobApplication) -> JobApplication:
        self.applications[application.id] = application
        return application

    async def get_by_id(
        self, tenant_id: uuid.UUID, application_id: uuid.UUID
    ) -> JobApplication | None:
        app = self.applications.get(application_id)
        return app if app and app.tenant_id == tenant_id else None

    async def get_by_source_provider_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, provider_id: str
    ) -> JobApplication | None:
        for app in self.applications.values():
            if (
                app.tenant_id == tenant_id
                and app.user_id == user_id
                and app.source_provider_id == provider_id
            ):
                return app
        return None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[JobApplication]:
        apps = [
            a
            for a in self.applications.values()
            if a.tenant_id == tenant_id and a.user_id == user_id
        ]
        return sorted(apps, key=lambda a: a.updated_at, reverse=True)

    async def list_tracked_provider_ids(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> set[str]:
        return {
            a.source_provider_id
            for a in self.applications.values()
            if a.tenant_id == tenant_id and a.user_id == user_id and a.source_provider_id
        }

    async def update(self, application: JobApplication) -> JobApplication:
        self.applications[application.id] = application
        return application

    async def soft_delete(self, tenant_id: uuid.UUID, application_id: uuid.UUID) -> None:
        self.applications.pop(application_id, None)


class FakeRecruiterContactRepository:
    def __init__(self) -> None:
        self.contacts: dict[uuid.UUID, RecruiterContact] = {}

    async def create(self, contact: RecruiterContact) -> RecruiterContact:
        self.contacts[contact.id] = contact
        return contact

    async def get_by_id(self, tenant_id: uuid.UUID, contact_id: uuid.UUID) -> RecruiterContact | None:
        c = self.contacts.get(contact_id)
        return c if c and c.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[RecruiterContact]:
        return [
            c for c in self.contacts.values() if c.tenant_id == tenant_id and c.user_id == user_id
        ]

    async def update(self, contact: RecruiterContact) -> RecruiterContact:
        self.contacts[contact.id] = contact
        return contact

    async def soft_delete(self, tenant_id: uuid.UUID, contact_id: uuid.UUID) -> None:
        self.contacts.pop(contact_id, None)


@pytest.fixture
def service() -> tuple[JobApplicationService, FakeJobApplicationRepository, FakeRecruiterContactRepository]:
    apps_repo = FakeJobApplicationRepository()
    recruiters_repo = FakeRecruiterContactRepository()
    return JobApplicationService(apps_repo, recruiters_repo), apps_repo, recruiters_repo


class TestCreate:
    async def test_create_defaults_to_considering(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        app = await svc.create(
            tenant_id=tenant_id, user_id=user_id, company="Acme", role_title="Engineer"
        )

        assert app.status == "considering"
        assert app.status_changed_at is not None

    async def test_create_accepts_a_linked_jd_tailoring_session_id(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session_id = uuid.uuid4()

        app = await svc.create(
            tenant_id=tenant_id,
            user_id=user_id,
            company="Globex",
            role_title="Engineer",
            jd_tailoring_session_id=session_id,
        )

        assert app.jd_tailoring_session_id == session_id

    async def test_create_rejects_a_recruiter_owned_by_another_user(self, service) -> None:
        svc, _, recruiters_repo = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(UTC)
        recruiter = await recruiters_repo.create(
            RecruiterContact(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=owner,
                name="Jane",
                created_at=now,
                updated_at=now,
            )
        )

        with pytest.raises(NotFoundError):
            await svc.create(
                tenant_id=tenant_id,
                user_id=other,
                company="Acme",
                role_title="Engineer",
                recruiter_id=recruiter.id,
            )


class TestGetOrCreateFromListing:
    async def test_creates_a_new_application_the_first_time(self, service) -> None:
        svc, apps_repo, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        app = await svc.get_or_create_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_tailoring_session_id=uuid.uuid4(),
        )

        assert app.source_provider_id == "adzuna-1"
        assert len(apps_repo.applications) == 1

    async def test_reuses_the_existing_application_without_repointing_the_session(
        self, service
    ) -> None:
        svc, apps_repo, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        first_session_id = uuid.uuid4()

        first = await svc.get_or_create_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_tailoring_session_id=first_session_id,
        )

        second_session_id = uuid.uuid4()
        second = await svc.get_or_create_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_tailoring_session_id=second_session_id,
        )

        assert second.id == first.id
        assert second.jd_tailoring_session_id == first_session_id
        assert len(apps_repo.applications) == 1


class TestUpdate:
    async def test_status_change_bumps_status_changed_at(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        app = await svc.create(
            tenant_id=tenant_id, user_id=user_id, company="Acme", role_title="Engineer"
        )
        original_changed_at = app.status_changed_at

        updated = await svc.update(
            tenant_id=tenant_id,
            user_id=user_id,
            application_id=app.id,
            company="Acme",
            role_title="Engineer",
            status="applied",
            target_role_id=None,
            applied_at=None,
            notes=None,
            recruiter_id=None,
        )

        assert updated.status == "applied"
        assert updated.status_changed_at >= original_changed_at

    async def test_same_status_does_not_bump_status_changed_at(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        app = await svc.create(
            tenant_id=tenant_id, user_id=user_id, company="Acme", role_title="Engineer"
        )
        original_changed_at = app.status_changed_at

        updated = await svc.update(
            tenant_id=tenant_id,
            user_id=user_id,
            application_id=app.id,
            company="Acme",
            role_title="Senior Engineer",
            status="considering",
            target_role_id=None,
            applied_at=None,
            notes="updated title",
            recruiter_id=None,
        )

        assert updated.role_title == "Senior Engineer"
        assert updated.status_changed_at == original_changed_at

    async def test_cannot_update_another_users_application(self, service) -> None:
        svc, _, _ = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        app = await svc.create(
            tenant_id=tenant_id, user_id=owner, company="Acme", role_title="Engineer"
        )

        with pytest.raises(NotFoundError):
            await svc.update(
                tenant_id=tenant_id,
                user_id=other,
                application_id=app.id,
                company="Acme",
                role_title="Engineer",
                status="applied",
                target_role_id=None,
                applied_at=None,
                notes=None,
                recruiter_id=None,
            )


class TestUnlinkAndDelete:
    async def test_unlink_clears_session_but_keeps_the_application(self, service) -> None:
        svc, apps_repo, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session_id = uuid.uuid4()
        app = await svc.get_or_create_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_tailoring_session_id=session_id,
        )

        updated = await svc.unlink_session(
            tenant_id=tenant_id, user_id=user_id, application_id=app.id
        )

        assert updated.jd_tailoring_session_id is None
        assert updated.company == "Acme"
        assert app.id in apps_repo.applications

    async def test_delete_removes_the_application(self, service) -> None:
        svc, apps_repo, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        app = await svc.create(
            tenant_id=tenant_id, user_id=user_id, company="Acme", role_title="Engineer"
        )

        await svc.delete(tenant_id=tenant_id, user_id=user_id, application_id=app.id)

        assert app.id not in apps_repo.applications
