"""Job Application Dashboard summary — live-computed per request, no
batch job (exact InterviewPrepSummaryService precedent: reasonable at
this app's per-user data volumes).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from app.domain.job_application_tracking.entities import (
    TERMINAL_STATUSES,
    JobApplicationStatus,
)
from app.domain.job_application_tracking.repositories import JobApplicationRepository

#: Per-stage "stuck too long" thresholds — proposed defaults (see the
#: implementation plan for rationale per stage), easy to tune once seen
#: in real use. Only non-terminal statuses are ever flagged.
_STUCK_THRESHOLD_DAYS: dict[JobApplicationStatus, int] = {
    "considering": 14,
    "applied": 10,
    "phone_screen": 5,
    "interview": 7,
    "other": 14,
}
_MAX_STUCK_EXAMPLES = 3


@dataclass(slots=True)
class StatusCount:
    status: JobApplicationStatus
    count: int


@dataclass(slots=True)
class NextInterview:
    application_id: UUID
    company: str
    role_title: str
    stage_label: str
    round_date: date


@dataclass(slots=True)
class StuckApplication:
    application_id: UUID
    company: str
    role_title: str
    status: JobApplicationStatus
    days_in_status: int


@dataclass(slots=True)
class JobApplicationSummary:
    status_counts: list[StatusCount]
    next_interview: NextInterview | None
    stuck_count: int
    stuck_examples: list[StuckApplication]


class JobApplicationSummaryService:
    def __init__(self, applications: JobApplicationRepository) -> None:
        self._applications = applications

    async def get_summary(self, tenant_id: UUID, user_id: UUID) -> JobApplicationSummary:
        applications = await self._applications.list_for_user(tenant_id, user_id)

        counts: dict[JobApplicationStatus, int] = {}
        for app in applications:
            counts[app.status] = counts.get(app.status, 0) + 1
        status_counts = [
            StatusCount(status=status, count=count) for status, count in counts.items()
        ]

        today = datetime.now(UTC).date()
        next_interview: NextInterview | None = None
        for app in applications:
            if app.status in TERMINAL_STATUSES:
                continue
            for round_ in app.interview_rounds:
                if round_.round_date is None or round_.round_date < today:
                    continue
                if next_interview is None or round_.round_date < next_interview.round_date:
                    next_interview = NextInterview(
                        application_id=app.id,
                        company=app.company,
                        role_title=app.role_title,
                        stage_label=round_.stage_label,
                        round_date=round_.round_date,
                    )

        stuck: list[StuckApplication] = []
        for app in applications:
            if app.status in TERMINAL_STATUSES:
                continue
            threshold = _STUCK_THRESHOLD_DAYS.get(app.status)
            if threshold is None:
                continue
            days_in_status = (today - app.status_changed_at.date()).days
            if days_in_status >= threshold:
                stuck.append(
                    StuckApplication(
                        application_id=app.id,
                        company=app.company,
                        role_title=app.role_title,
                        status=app.status,
                        days_in_status=days_in_status,
                    )
                )

        return JobApplicationSummary(
            status_counts=status_counts,
            next_interview=next_interview,
            stuck_count=len(stuck),
            stuck_examples=stuck[:_MAX_STUCK_EXAMPLES],
        )
