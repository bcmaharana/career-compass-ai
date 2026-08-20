"""Job Application application service.

Flat, user_id-scoped (LearningItemService's shape, not a
career_profile_id one) — a job application is for one real job at one
company, not "for" a profile. `_get_owned_or_raise` follows the same
not-found-not-forbidden convention every other domain in this app uses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import JobApplication, JobApplicationStatus
from app.domain.job_application_tracking.repositories import (
    JobApplicationRepository,
    RecruiterContactRepository,
)


class JobApplicationService:
    def __init__(
        self, applications: JobApplicationRepository, recruiters: RecruiterContactRepository
    ) -> None:
        self._applications = applications
        self._recruiters = recruiters

    async def _get_owned_or_raise(
        self, tenant_id: UUID, user_id: UUID, application_id: UUID
    ) -> JobApplication:
        application = await self._applications.get_by_id(tenant_id, application_id)
        if application is None or application.user_id != user_id:
            raise NotFoundError("Job application not found.", code="JOB_APPLICATION_NOT_FOUND")
        return application

    async def _check_recruiter_owned(
        self, tenant_id: UUID, user_id: UUID, recruiter_id: UUID | None
    ) -> None:
        if recruiter_id is None:
            return
        recruiter = await self._recruiters.get_by_id(tenant_id, recruiter_id)
        if recruiter is None or recruiter.user_id != user_id:
            raise NotFoundError("Recruiter contact not found.", code="RECRUITER_CONTACT_NOT_FOUND")

    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        company: str,
        role_title: str,
        target_role_id: UUID | None = None,
        status: JobApplicationStatus = "considering",
        applied_at: date | None = None,
        notes: str | None = None,
        recruiter_id: UUID | None = None,
        jd_tailoring_session_id: UUID | None = None,
    ) -> JobApplication:
        await self._check_recruiter_owned(tenant_id, user_id, recruiter_id)
        now = datetime.now(UTC)
        return await self._applications.create(
            JobApplication(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                company=company,
                role_title=role_title,
                status=status,
                status_changed_at=now,
                created_at=now,
                updated_at=now,
                target_role_id=target_role_id,
                applied_at=applied_at,
                notes=notes,
                jd_tailoring_session_id=jd_tailoring_session_id,
                recruiter_id=recruiter_id,
            )
        )

    async def get_or_create_from_listing(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        provider_id: str,
        title: str,
        company: str,
        redirect_url: str,
        jd_tailoring_session_id: UUID,
    ) -> JobApplication:
        """If this listing is already tracked, returns the existing
        application as-is — does NOT repoint its jd_tailoring_session_id
        to the new session. A user re-evaluating an already-tracked
        listing (e.g. after editing the JD text) shouldn't cause the
        tracker to silently jump to a different conversation; the first
        session that started tracking stays canonical."""
        existing = await self._applications.get_by_source_provider_id(
            tenant_id, user_id, provider_id
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        return await self._applications.create(
            JobApplication(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                company=company,
                role_title=title,
                status="considering",
                status_changed_at=now,
                created_at=now,
                updated_at=now,
                target_role_id=target_role_id,
                source_provider_id=provider_id,
                source_title=title,
                source_company=company,
                source_redirect_url=redirect_url,
                jd_tailoring_session_id=jd_tailoring_session_id,
            )
        )

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JobApplication]:
        return await self._applications.list_for_user(tenant_id, user_id)

    async def list_tracked_provider_ids(self, tenant_id: UUID, user_id: UUID) -> set[str]:
        return await self._applications.list_tracked_provider_ids(tenant_id, user_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        application_id: UUID,
        company: str,
        role_title: str,
        status: JobApplicationStatus,
        target_role_id: UUID | None,
        applied_at: date | None,
        notes: str | None,
        recruiter_id: UUID | None,
    ) -> JobApplication:
        application = await self._get_owned_or_raise(tenant_id, user_id, application_id)
        await self._check_recruiter_owned(tenant_id, user_id, recruiter_id)
        application.company = company
        application.role_title = role_title
        if status != application.status:
            application.status_changed_at = datetime.now(UTC)
        application.status = status
        application.target_role_id = target_role_id
        application.applied_at = applied_at
        application.notes = notes
        application.recruiter_id = recruiter_id
        return await self._applications.update(application)

    async def unlink_session(
        self, *, tenant_id: UUID, user_id: UUID, application_id: UUID
    ) -> JobApplication:
        """Clears jd_tailoring_session_id only — status/company/source
        snapshot fields are untouched, the application stays tracked.
        Never touches jd_tailoring_sessions/jd_tailoring_messages at all
        (the FK direction means acting on this child can never affect
        the session)."""
        application = await self._get_owned_or_raise(tenant_id, user_id, application_id)
        application.jd_tailoring_session_id = None
        return await self._applications.update(application)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, application_id: UUID) -> None:
        await self._get_owned_or_raise(tenant_id, user_id, application_id)
        await self._applications.soft_delete(tenant_id, application_id)
