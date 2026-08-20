"""Unit tests for JobApplicationSummaryService — fake repository, no
database. Live-computed aggregation, exact InterviewPrepSummaryService
precedent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.application.job_application_tracking.job_application_summary_service import (
    JobApplicationSummaryService,
)
from app.domain.job_application_tracking.entities import InterviewRound, JobApplication

pytestmark = pytest.mark.unit

_TODAY = datetime.now(UTC).date()


class FakeJobApplicationRepository:
    def __init__(self, applications: list[JobApplication]) -> None:
        self._applications = applications

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[JobApplication]:
        return self._applications


def _make_application(
    *, status: str, status_changed_at: datetime, rounds: list[InterviewRound] | None = None
) -> JobApplication:
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    return JobApplication(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        company="Acme",
        role_title="Engineer",
        status=status,  # type: ignore[arg-type]
        status_changed_at=status_changed_at,
        created_at=now,
        updated_at=now,
        interview_rounds=rounds or [],
    )


def _make_round(*, job_application_id: uuid.UUID, round_date: date | None, stage_label: str) -> InterviewRound:
    now = datetime.now(UTC)
    return InterviewRound(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_application_id=job_application_id,
        stage_label=stage_label,
        display_order=1,
        created_at=now,
        updated_at=now,
        round_date=round_date,
    )


class TestStatusCounts:
    async def test_counts_per_status(self) -> None:
        apps = [
            _make_application(status="considering", status_changed_at=datetime.now(UTC)),
            _make_application(status="considering", status_changed_at=datetime.now(UTC)),
            _make_application(status="applied", status_changed_at=datetime.now(UTC)),
        ]
        service = JobApplicationSummaryService(FakeJobApplicationRepository(apps))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        counts = {sc.status: sc.count for sc in summary.status_counts}
        assert counts == {"considering": 2, "applied": 1}


class TestNextInterview:
    async def test_picks_the_soonest_upcoming_round_across_applications(self) -> None:
        app1 = _make_application(status="interview", status_changed_at=datetime.now(UTC))
        app2 = _make_application(status="interview", status_changed_at=datetime.now(UTC))
        app1.interview_rounds = [
            _make_round(job_application_id=app1.id, round_date=_TODAY + timedelta(days=10), stage_label="Onsite")
        ]
        app2.interview_rounds = [
            _make_round(job_application_id=app2.id, round_date=_TODAY + timedelta(days=3), stage_label="Screen")
        ]
        service = JobApplicationSummaryService(FakeJobApplicationRepository([app1, app2]))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.next_interview is not None
        assert summary.next_interview.application_id == app2.id
        assert summary.next_interview.stage_label == "Screen"

    async def test_ignores_past_rounds_and_terminal_applications(self) -> None:
        app = _make_application(status="rejected", status_changed_at=datetime.now(UTC))
        app.interview_rounds = [
            _make_round(job_application_id=app.id, round_date=_TODAY + timedelta(days=1), stage_label="Onsite")
        ]
        past_app = _make_application(status="interview", status_changed_at=datetime.now(UTC))
        past_app.interview_rounds = [
            _make_round(job_application_id=past_app.id, round_date=_TODAY - timedelta(days=1), stage_label="Screen")
        ]
        service = JobApplicationSummaryService(FakeJobApplicationRepository([app, past_app]))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.next_interview is None


class TestStuckApplications:
    async def test_flags_applications_past_their_stage_threshold(self) -> None:
        # "applied" threshold is 10 days.
        stuck = _make_application(
            status="applied", status_changed_at=datetime.now(UTC) - timedelta(days=11)
        )
        fresh = _make_application(
            status="applied", status_changed_at=datetime.now(UTC) - timedelta(days=2)
        )
        service = JobApplicationSummaryService(FakeJobApplicationRepository([stuck, fresh]))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.stuck_count == 1
        assert summary.stuck_examples[0].application_id == stuck.id

    async def test_terminal_statuses_are_never_flagged(self) -> None:
        old_rejected = _make_application(
            status="rejected", status_changed_at=datetime.now(UTC) - timedelta(days=365)
        )
        service = JobApplicationSummaryService(FakeJobApplicationRepository([old_rejected]))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.stuck_count == 0

    async def test_caps_stuck_examples_at_three(self) -> None:
        apps = [
            _make_application(status="applied", status_changed_at=datetime.now(UTC) - timedelta(days=30))
            for _ in range(5)
        ]
        service = JobApplicationSummaryService(FakeJobApplicationRepository(apps))

        summary = await service.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.stuck_count == 5
        assert len(summary.stuck_examples) == 3
