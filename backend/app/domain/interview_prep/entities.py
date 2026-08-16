"""Interview Preparation domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/career_profile/entities.py.

Both InterviewTopic and InterviewQuestion are scoped by `target_role_id:
UUID | None` — None = generic/Master-scoped, a real id = tied to that
specific Target Role, exactly the same split CareerProfile itself uses
(two fully independent scopes, not a filter/view over one shared list).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class ReferenceLink:
    """A labeled external URL attached to an InterviewQuestion — a label
    reads far better in the UI than a bare link, so this is a small
    value type rather than a plain list[str] (contrast
    TargetRole.required_skills, which has no per-item metadata and so
    stays a plain string list)."""

    url: str
    label: str


@dataclass(slots=True)
class InterviewTopic:
    """A study-notes card: a name, optional free-text discussion, and an
    optional image (stored in the private object storage bucket — see
    app/domain/resume_intelligence/storage.py's PrivateObjectStorageRepository,
    reused here rather than introducing a third bucket). `section` is a
    plain free-text grouping label with no separate entity of its own —
    same "just a string on each item" pattern CoreCompetency.category
    already uses for Core Competencies/My Skills.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role_id: UUID | None  # None = generic/Master-scoped
    name: str
    display_order: int
    created_at: datetime
    updated_at: datetime
    section: str | None = None
    discussion: str | None = None
    image_key: str | None = None  # private-bucket storage key, not a URL
    reference_links: list[ReferenceLink] = field(default_factory=list)
    deleted_at: datetime | None = None


@dataclass(slots=True)
class InterviewQuestion:
    """An interview question with a place for the user's own answer, an
    AI-generated one (read-only, regenerate-only — see
    InterviewAnswerService), a list of labeled reference links, and an
    optional link to one of this scope's InterviewTopics.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role_id: UUID | None  # None = generic/Master-scoped
    question: str
    display_order: int
    created_at: datetime
    updated_at: datetime
    topic_id: UUID | None = None
    manual_answer: str | None = None
    ai_answer: str | None = None
    #: None = never generated. "generated" | "failed".
    ai_answer_status: str | None = None
    ai_answer_error: str | None = None
    ai_answer_generated_at: datetime | None = None
    reference_links: list[ReferenceLink] = field(default_factory=list)
    deleted_at: datetime | None = None
