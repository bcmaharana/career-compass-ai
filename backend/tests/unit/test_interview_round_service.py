"""Unit tests for InterviewRoundService — fake repositories, no
database. Ownership walks through the parent JobApplication.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.job_application_tracking.interview_round_service import (
    InterviewRoundService,
)
from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import InterviewRound, JobApplication

pytestmark = pytest.mark.unit


class FakeJobApplicationRepository:
    def __init__(self) -> None:
        self.applications: dict[uuid.UUID, JobApplication] = {}

    async def create(self, application: JobApplication) -> JobApplication:
        self.applications[application.id] = application
        return application

    async def get_by_id(self, tenant_id: uuid.UUID, application_id: uuid.UUID):
        app = self.applications.get(application_id)
        return app if app and app.tenant_id == tenant_id else None


class FakeInterviewRoundRepository:
    def __init__(self) -> None:
        self.rounds: dict[uuid.UUID, InterviewRound] = {}
        self._next_order = 1

    async def create(self, round_: InterviewRound) -> InterviewRound:
        round_.display_order = self._next_order
        self._next_order += 1
        self.rounds[round_.id] = round_
        return round_

    async def get_by_id(self, tenant_id: uuid.UUID, round_id: uuid.UUID) -> InterviewRound | None:
        r = self.rounds.get(round_id)
        return r if r and r.tenant_id == tenant_id else None

    async def update(self, round_: InterviewRound) -> InterviewRound:
        self.rounds[round_.id] = round_
        return round_

    async def soft_delete(self, tenant_id: uuid.UUID, round_id: uuid.UUID) -> None:
        self.rounds.pop(round_id, None)

    async def move(self, tenant_id: uuid.UUID, round_id: uuid.UUID, direction: str) -> None:
        target = self.rounds[round_id]
        siblings = sorted(
            (r for r in self.rounds.values() if r.job_application_id == target.job_application_id),
            key=lambda r: r.display_order,
        )
        index = next(i for i, r in enumerate(siblings) if r.id == round_id)
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(siblings):
            return
        current, neighbor = siblings[index], siblings[neighbor_index]
        current.display_order, neighbor.display_order = neighbor.display_order, current.display_order


async def _make_application(apps_repo: FakeJobApplicationRepository, tenant_id, user_id) -> JobApplication:
    now = datetime.now(UTC)
    return await apps_repo.create(
        JobApplication(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            company="Acme",
            role_title="Engineer",
            status="considering",
            status_changed_at=now,
            created_at=now,
            updated_at=now,
        )
    )


@pytest.fixture
def service():
    rounds_repo = FakeInterviewRoundRepository()
    apps_repo = FakeJobApplicationRepository()
    return InterviewRoundService(rounds_repo, apps_repo), rounds_repo, apps_repo


class TestAddAndUpdate:
    async def test_add_creates_a_round(self, service) -> None:
        svc, _, apps_repo = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        app = await _make_application(apps_repo, tenant_id, user_id)

        round_ = await svc.add(
            tenant_id=tenant_id,
            user_id=user_id,
            application_id=app.id,
            stage_label="Phone Screen",
        )

        assert round_.stage_label == "Phone Screen"
        assert round_.job_application_id == app.id

    async def test_cannot_add_to_another_users_application(self, service) -> None:
        svc, _, apps_repo = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        app = await _make_application(apps_repo, tenant_id, owner)

        with pytest.raises(NotFoundError):
            await svc.add(
                tenant_id=tenant_id,
                user_id=other,
                application_id=app.id,
                stage_label="Phone Screen",
            )

    async def test_cannot_update_a_round_owned_by_another_user(self, service) -> None:
        svc, _, apps_repo = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        app = await _make_application(apps_repo, tenant_id, owner)
        round_ = await svc.add(
            tenant_id=tenant_id, user_id=owner, application_id=app.id, stage_label="Phone Screen"
        )

        with pytest.raises(NotFoundError):
            await svc.update(
                tenant_id=tenant_id,
                user_id=other,
                round_id=round_.id,
                stage_label="Onsite",
                round_date=None,
                interviewer_name=None,
                interviewer_title=None,
                notes=None,
            )


class TestMove:
    async def test_move_swaps_display_order_among_siblings(self, service) -> None:
        svc, _, apps_repo = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        app = await _make_application(apps_repo, tenant_id, user_id)
        first = await svc.add(
            tenant_id=tenant_id, user_id=user_id, application_id=app.id, stage_label="Screen"
        )
        second = await svc.add(
            tenant_id=tenant_id, user_id=user_id, application_id=app.id, stage_label="Onsite"
        )

        await svc.move(tenant_id=tenant_id, user_id=user_id, round_id=second.id, direction="up")

        assert second.display_order < first.display_order
