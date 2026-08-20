"""JD Tailoring domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/learning_intelligence/entities.py.

A JdTailoringSession is a real multi-turn conversation grounded in one
job description, scoped to a career profile (Master or a Target Role
Profile). Deliberately NOT built on the existing app/domain/chat/
tables — ChatConversationRepository's own docstring states "there's
deliberately no 'start a new conversation' affordance anywhere in this
app today, so a user only ever has one conversation in practice," which
is the wrong shape for a per-JD, saved-with-history session a user may
have several of at once. This reuses ChatService.send_message()'s
*pattern* (history render -> LLM call -> graceful degrade), not its
tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

#: 'job_listing' sessions snapshot an Opportunity Intelligence listing's
#: fields (provider_id/title/company/redirect_url) at creation time,
#: since job_listing_cache is an ephemeral, 24h-TTL cache with no stable
#: per-listing row to reference. 'custom' sessions have none of that —
#: the user pasted a JD with no Adzuna listing behind it at all.
SourceType = Literal["job_listing", "custom"]

#: None while never generated. Set on every generate attempt, success or
#: failure — mirrors InterviewQuestion.ai_answer_status's shape.
TailoredResumeStatus = Literal["generated", "failed"]


class JdTailoringMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(slots=True)
class JdTailoringSession:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    source_type: SourceType
    jd_text: str
    created_at: datetime
    updated_at: datetime
    #: None = Master profile. A real id = that Target Role Profile.
    target_role_id: UUID | None = None
    #: Only set when source_type == "job_listing" — Adzuna's own id, so
    #: the source cache row (24h TTL, may have since expired/changed) is
    #: never the source of truth for this session again.
    source_provider_id: str | None = None
    #: Set for BOTH source types, despite the name — a "custom" session
    #: has real company/role_title too (AI-extracted, gaps filled in by
    #: hand), and without it the session history list would have nothing
    #: to show every custom session as beyond an indistinguishable
    #: "Custom JD." Only source_redirect_url below is job_listing-only.
    source_title: str | None = None
    source_company: str | None = None
    source_redirect_url: str | None = None
    tailored_resume_docx_key: str | None = None
    tailored_resume_pdf_key: str | None = None
    #: The last structured AI output (headline/summary/experience_bullets)
    #: kept for audit/debugging — not read back by anything at request time.
    tailored_resume_content: dict[str, object] | None = None
    tailored_resume_status: TailoredResumeStatus | None = None
    tailored_resume_error: str | None = None
    tailored_resume_generated_at: datetime | None = None
    deleted_at: datetime | None = None


@dataclass(slots=True)
class JdTailoringMessage:
    id: UUID
    tenant_id: UUID
    session_id: UUID
    role: JdTailoringMessageRole
    content: str
    created_at: datetime
