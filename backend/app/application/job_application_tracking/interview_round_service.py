"""Interview Round application service — ownership walks through the
parent JobApplication (a round has no independent access path of its
own), reading the JobApplicationRepository directly rather than
depending on JobApplicationService, same "take the raw repository, not
another application service" shape ResumeExportService uses for its
own read-only cross-entity needs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import InterviewRound
from app.domain.job_application_tracking.repositories import (
    Direction,
    InterviewRoundRepository,
    JobApplicationRepository,
)


class InterviewRoundService:
    def __init__(
        self, rounds: InterviewRoundRepository, applications: JobApplicationRepository
    ) -> None:
        self._rounds = rounds
        self._applications = applications

    async def _get_owned_application_or_raise(
        self, tenant_id: UUID, user_id: UUID, application_id: UUID
    ) -> None:
        application = await self._applications.get_by_id(tenant_id, application_id)
        if application is None or application.user_id != user_id:
            raise NotFoundError("Job application not found.", code="JOB_APPLICATION_NOT_FOUND")

    async def _get_owned_round_or_raise(
        self, tenant_id: UUID, user_id: UUID, round_id: UUID
    ) -> InterviewRound:
        round_ = await self._rounds.get_by_id(tenant_id, round_id)
        if round_ is None or round_.user_id != user_id:
            raise NotFoundError("Interview round not found.", code="INTERVIEW_ROUND_NOT_FOUND")
        return round_

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        application_id: UUID,
        stage_label: str,
        round_date: date | None = None,
        interviewer_name: str | None = None,
        interviewer_title: str | None = None,
        notes: str | None = None,
    ) -> InterviewRound:
        await self._get_owned_application_or_raise(tenant_id, user_id, application_id)
        now = datetime.now(UTC)
        return await self._rounds.create(
            InterviewRound(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                job_application_id=application_id,
                stage_label=stage_label,
                display_order=0,
                created_at=now,
                updated_at=now,
                round_date=round_date,
                interviewer_name=interviewer_name,
                interviewer_title=interviewer_title,
                notes=notes,
            )
        )

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        round_id: UUID,
        stage_label: str,
        round_date: date | None,
        interviewer_name: str | None,
        interviewer_title: str | None,
        notes: str | None,
    ) -> InterviewRound:
        round_ = await self._get_owned_round_or_raise(tenant_id, user_id, round_id)
        round_.stage_label = stage_label
        round_.round_date = round_date
        round_.interviewer_name = interviewer_name
        round_.interviewer_title = interviewer_title
        round_.notes = notes
        return await self._rounds.update(round_)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, round_id: UUID) -> None:
        await self._get_owned_round_or_raise(tenant_id, user_id, round_id)
        await self._rounds.soft_delete(tenant_id, round_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, round_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_round_or_raise(tenant_id, user_id, round_id)
        await self._rounds.move(tenant_id, round_id, direction)
