"""Unit tests for JdTailoringIntakeService — fakes the two application
services it orchestrates, no database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.jd_tailoring.jd_tailoring_intake_service import JdTailoringIntakeService
from app.domain.jd_tailoring.entities import JdTailoringSession
from app.domain.job_application_tracking.entities import JobApplication

pytestmark = pytest.mark.unit


class FakeSessionService:
    def __init__(self) -> None:
        self.start_from_listing_calls = 0
        self.start_custom_calls = 0

    async def start_from_listing(self, **kwargs) -> JdTailoringSession:
        self.start_from_listing_calls += 1
        now = datetime.now(UTC)
        return JdTailoringSession(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            user_id=kwargs["user_id"],
            source_type="job_listing",
            jd_text=kwargs["jd_text"],
            created_at=now,
            updated_at=now,
            target_role_id=kwargs["target_role_id"],
            source_provider_id=kwargs["provider_id"],
            source_title=kwargs["title"],
            source_company=kwargs["company"],
            source_redirect_url=kwargs["redirect_url"],
        )

    async def start_custom(self, **kwargs) -> JdTailoringSession:
        self.start_custom_calls += 1
        now = datetime.now(UTC)
        return JdTailoringSession(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            user_id=kwargs["user_id"],
            source_type="custom",
            source_title=kwargs.get("role_title"),
            source_company=kwargs.get("company"),
            jd_text=kwargs["jd_text"],
            created_at=now,
            updated_at=now,
            target_role_id=kwargs["target_role_id"],
        )


class FakeJobApplicationService:
    def __init__(self, existing: JobApplication | None = None) -> None:
        self._existing = existing
        self.get_or_create_calls: list[dict[str, object]] = []
        self.create_calls: list[dict[str, object]] = []

    async def get_or_create_from_listing(self, **kwargs) -> JobApplication:
        self.get_or_create_calls.append(kwargs)
        if self._existing is not None:
            return self._existing
        now = datetime.now(UTC)
        return JobApplication(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            user_id=kwargs["user_id"],
            company=kwargs["company"],
            role_title=kwargs["title"],
            status="considering",
            status_changed_at=now,
            created_at=now,
            updated_at=now,
            source_provider_id=kwargs["provider_id"],
            jd_tailoring_session_id=kwargs["jd_tailoring_session_id"],
        )

    async def create(self, **kwargs) -> JobApplication:
        self.create_calls.append(kwargs)
        now = datetime.now(UTC)
        return JobApplication(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            user_id=kwargs["user_id"],
            company=kwargs["company"],
            role_title=kwargs["role_title"],
            status="considering",
            status_changed_at=now,
            created_at=now,
            updated_at=now,
            target_role_id=kwargs.get("target_role_id"),
            jd_tailoring_session_id=kwargs.get("jd_tailoring_session_id"),
        )


class TestStartFromListing:
    async def test_creates_a_session_and_a_linked_application(self) -> None:
        session_service = FakeSessionService()
        job_application_service = FakeJobApplicationService()
        intake = JdTailoringIntakeService(session_service, job_application_service)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        result = await intake.start_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_text="JD text",
        )

        assert result.session.source_provider_id == "adzuna-1"
        assert result.job_application.jd_tailoring_session_id == result.session.id
        assert job_application_service.get_or_create_calls[0]["jd_tailoring_session_id"] == result.session.id

    async def test_a_second_session_against_the_same_listing_does_not_repoint_the_existing_application(
        self,
    ) -> None:
        # JobApplicationService.get_or_create_from_listing itself decides
        # not to repoint (see its own unit test) — this test just proves
        # the orchestrator passes the NEW session id through and trusts
        # whatever the fake job-application service returns, rather than
        # doing any repointing logic of its own.
        existing_application = JobApplication(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            company="Acme",
            role_title="Engineer",
            status="considering",
            status_changed_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            source_provider_id="adzuna-1",
            jd_tailoring_session_id=uuid.uuid4(),  # the FIRST session's id
        )
        session_service = FakeSessionService()
        job_application_service = FakeJobApplicationService(existing=existing_application)
        intake = JdTailoringIntakeService(session_service, job_application_service)

        result = await intake.start_from_listing(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_text="A second look at the JD",
        )

        assert session_service.start_from_listing_calls == 1
        # A brand-new session was created, but the returned application
        # is still the pre-existing one, still pointing at the original
        # session id — not the one just created.
        assert result.job_application.jd_tailoring_session_id != result.session.id
        assert result.job_application.id == existing_application.id


class TestStartCustom:
    async def test_creates_a_session_and_a_linked_application_using_given_company_and_role(
        self,
    ) -> None:
        session_service = FakeSessionService()
        job_application_service = FakeJobApplicationService()
        intake = JdTailoringIntakeService(session_service, job_application_service)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        result = await intake.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="A JD found outside Opportunity Intelligence.",
            company="Globex",
            role_title="Platform Engineer",
        )

        assert result.session.source_type == "custom"
        assert result.session.source_title == "Platform Engineer"
        assert result.session.source_company == "Globex"
        assert result.job_application.company == "Globex"
        assert result.job_application.role_title == "Platform Engineer"
        assert result.job_application.jd_tailoring_session_id == result.session.id
        assert session_service.start_custom_calls == 1
        assert len(job_application_service.create_calls) == 1

    async def test_each_custom_session_creates_its_own_application_no_dedupe(self) -> None:
        # Unlike start_from_listing, there is no provider_id to dedupe
        # against for a pasted JD — every call is a genuinely new
        # application.
        session_service = FakeSessionService()
        job_application_service = FakeJobApplicationService()
        intake = JdTailoringIntakeService(session_service, job_application_service)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await intake.start_custom(
            tenant_id=tenant_id, user_id=user_id, target_role_id=None,
            jd_text="First JD", company="Globex", role_title="Engineer",
        )
        second = await intake.start_custom(
            tenant_id=tenant_id, user_id=user_id, target_role_id=None,
            jd_text="Second JD", company="Globex", role_title="Engineer",
        )

        assert first.job_application.id != second.job_application.id
        assert len(job_application_service.create_calls) == 2
