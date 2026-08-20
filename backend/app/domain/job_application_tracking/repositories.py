"""Repository interfaces for the Job Application Tracking bounded
context.

Application services depend only on these Protocols — see
app/domain/learning_intelligence/repositories.py for the established
pattern this follows.
"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from app.domain.job_application_tracking.entities import (
    InterviewRound,
    JobApplication,
    RecruiterContact,
)

#: Declared locally, not imported from app.adapters.db.reorder — domain/
#: must have zero adapter imports. Same duplication precedent as
#: app/domain/learning_intelligence/repositories.py's own Direction alias.
Direction = Literal["up", "down"]


class JobApplicationRepository(Protocol):
    async def create(self, application: JobApplication) -> JobApplication: ...
    async def get_by_id(
        self, tenant_id: UUID, application_id: UUID
    ) -> JobApplication | None: ...
    async def get_by_source_provider_id(
        self, tenant_id: UUID, user_id: UUID, provider_id: str
    ) -> JobApplication | None:
        """The non-deleted application (if any) already tracking this
        exact Adzuna listing — used both for the auto-create dedupe and
        the Job Listing page's "Already tracking" badge lookup."""
        ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JobApplication]:
        """Sorted updated_at DESC — no manual reordering for this list
        (a job-application list doesn't fit the curated-section
        drag-order pattern). Each application's interview_rounds is
        populated via one batched extra query, not N+1."""
        ...
    async def list_tracked_provider_ids(self, tenant_id: UUID, user_id: UUID) -> set[str]:
        """Every source_provider_id this user has a non-deleted
        application for — backs the Job Listing page's per-row
        "Already tracking" badge without fetching full application
        rows."""
        ...
    async def update(self, application: JobApplication) -> JobApplication: ...
    async def soft_delete(self, tenant_id: UUID, application_id: UUID) -> None: ...


class InterviewRoundRepository(Protocol):
    async def create(self, round_: InterviewRound) -> InterviewRound: ...
    async def get_by_id(self, tenant_id: UUID, round_id: UUID) -> InterviewRound | None: ...
    async def update(self, round_: InterviewRound) -> InterviewRound: ...
    async def soft_delete(self, tenant_id: UUID, round_id: UUID) -> None: ...
    async def move(self, tenant_id: UUID, round_id: UUID, direction: Direction) -> None: ...


class RecruiterContactRepository(Protocol):
    async def create(self, contact: RecruiterContact) -> RecruiterContact: ...
    async def get_by_id(self, tenant_id: UUID, contact_id: UUID) -> RecruiterContact | None: ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[RecruiterContact]: ...
    async def update(self, contact: RecruiterContact) -> RecruiterContact: ...
    async def soft_delete(self, tenant_id: UUID, contact_id: UUID) -> None: ...
