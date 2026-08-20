"""Job Application Tracking domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/learning_intelligence/entities.py.

JobApplication is flat and user_id-scoped (not career_profile_id) — same
shape as LearningItem/CareerGoal, since a job application is for one
real job at one company, not "for" a profile the way curated profile
content is. InterviewRound is a one-to-many child (structured, its own
manual reorder) and RecruiterContact is a standalone, reusable entity
referenced by an optional single FK — not itself owned by any one
application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from uuid import UUID

#: Fixed pipeline, confirmed with the user (not user-customizable, same
#: "no user-managed vocabularies exist anywhere in this app" reasoning
#: as every other status-like field). Also the exact CHECK constraint
#: values on job_applications.status in the migration — keep both in
#: sync by hand if this ever changes.
JobApplicationStatus = Literal[
    "considering",
    "applied",
    "phone_screen",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    "didnt_hear_back",
    "other",
]

#: A status an application never moves out of — never flagged by the
#: Dashboard card's "stuck too long" nudge. Business logic (not a DB
#: constraint), so it lives here rather than duplicated between the
#: summary service and any future caller.
TERMINAL_STATUSES: frozenset[JobApplicationStatus] = frozenset(
    {"offer", "rejected", "withdrawn", "didnt_hear_back"}
)


@dataclass(slots=True)
class ContactHistoryEntry:
    """One dated note in a RecruiterContact's contact history — same
    "labeled value type, not a bare list" reasoning as
    app/domain/interview_prep/entities.py's ReferenceLink."""

    date: date
    note: str


@dataclass(slots=True)
class RecruiterContact:
    """Standalone, reusable across applications — creatable on its own
    (an address book), before any JobApplication ever references it."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    role_title: str | None = None
    contact_history: list[ContactHistoryEntry] = field(default_factory=list)
    deleted_at: datetime | None = None


@dataclass(slots=True)
class InterviewRound:
    """A single interview round attached to one JobApplication —
    date may be unknown/TBD, so ordering is a plain per-parent
    display_order column (same shape as InterviewQuestion.follow_ups'
    own ordering), not derived from round_date."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    job_application_id: UUID
    stage_label: str
    display_order: int
    created_at: datetime
    updated_at: datetime
    round_date: date | None = None
    interviewer_name: str | None = None
    interviewer_title: str | None = None
    notes: str | None = None
    deleted_at: datetime | None = None


@dataclass(slots=True)
class JobApplication:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    company: str
    role_title: str
    status: JobApplicationStatus
    #: Set to created_at at insert; bumped ONLY when status actually
    #: changes (not on every edit) — drives the per-stage stuck-nudge.
    status_changed_at: datetime
    created_at: datetime
    updated_at: datetime
    target_role_id: UUID | None = None
    #: Snapshot from job_listing_cache at auto-create time — no stable
    #: FK exists (see JdTailoringSession's own docstring for why).
    source_provider_id: str | None = None
    source_title: str | None = None
    source_company: str | None = None
    source_redirect_url: str | None = None
    jd_tailoring_session_id: UUID | None = None
    recruiter_id: UUID | None = None
    applied_at: date | None = None
    notes: str | None = None
    #: Populated by JobApplicationRepository.list_for_user() (one batched
    #: extra query, not N+1 — same _rounds_for_many shape as
    #: InterviewQuestion.follow_ups) — never persisted itself.
    interview_rounds: list[InterviewRound] = field(default_factory=list)
    deleted_at: datetime | None = None
