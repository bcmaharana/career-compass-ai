"""Orchestrates starting a JD Tailoring session together with
auto-creating its linked Job Application — mirrors ResumeMergeService's
"constructor takes application services, fans out" shape, not a
repository-level concern.

Both entry points auto-create a tracked application (confirmed with the
user: "the tracked application" needs Company/Role Title regardless of
source). The two paths differ only in where those fields and the dedupe
behavior come from:
- `start_from_listing`: company/role_title/provider_id/redirect_url all
  come from the Adzuna listing; a second session against the same
  listing reuses the existing application (see
  JobApplicationService.get_or_create_from_listing's own docstring).
- `start_custom`: no provider_id exists (a pasted JD has no stable
  listing identity), so there is nothing to dedupe against — every
  custom session unconditionally creates its own new application, using
  the company/role_title the frontend already resolved (AI-extracted,
  gaps filled in by hand).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.jd_tailoring.jd_tailoring_session_service import JdTailoringSessionService
from app.application.job_application_tracking.job_application_service import (
    JobApplicationService,
)
from app.domain.jd_tailoring.entities import JdTailoringSession
from app.domain.job_application_tracking.entities import JobApplication


@dataclass(slots=True)
class JdTailoringIntakeResult:
    session: JdTailoringSession
    job_application: JobApplication


class JdTailoringIntakeService:
    def __init__(
        self, sessions: JdTailoringSessionService, job_applications: JobApplicationService
    ) -> None:
        self._sessions = sessions
        self._job_applications = job_applications

    async def start_from_listing(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        provider_id: str,
        title: str,
        company: str,
        redirect_url: str,
        jd_text: str,
    ) -> JdTailoringIntakeResult:
        session = await self._sessions.start_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role_id,
            provider_id=provider_id,
            title=title,
            company=company,
            redirect_url=redirect_url,
            jd_text=jd_text,
        )
        job_application = await self._job_applications.get_or_create_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role_id,
            provider_id=provider_id,
            title=title,
            company=company,
            redirect_url=redirect_url,
            jd_tailoring_session_id=session.id,
        )
        return JdTailoringIntakeResult(session=session, job_application=job_application)

    async def start_custom(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        jd_text: str,
        company: str,
        role_title: str,
    ) -> JdTailoringIntakeResult:
        session = await self._sessions.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role_id,
            jd_text=jd_text,
            company=company,
            role_title=role_title,
        )
        job_application = await self._job_applications.create(
            tenant_id=tenant_id,
            user_id=user_id,
            company=company,
            role_title=role_title,
            target_role_id=target_role_id,
            jd_tailoring_session_id=session.id,
        )
        return JdTailoringIntakeResult(session=session, job_application=job_application)
