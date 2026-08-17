"""Request/response schemas for the Interview Preparation API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReferenceLinkPayload(BaseModel):
    url: str
    label: str


class InterviewTopicRequest(BaseModel):
    name: str
    section: str | None = None
    discussion: str | None = None
    #: Every scope (Master and/or one or more Target Roles — None
    #: entries mean Master) this topic should be tagged into and
    #: visible under. Must contain at least one entry (enforced by
    #: InterviewTopicService, not here, for the same consistent
    #: domain-exception-over-Pydantic-validator convention this app's
    #: other services already follow).
    scope_target_role_ids: list[UUID | None]


class InterviewTopicUpdateRequest(BaseModel):
    name: str
    section: str | None = None
    discussion: str | None = None
    reference_links: list[ReferenceLinkPayload] = []
    scope_target_role_ids: list[UUID | None]


class InterviewTopicResponse(BaseModel):
    id: UUID
    name: str
    section: str | None
    discussion: str | None
    image_url: str | None
    reference_links: list[ReferenceLinkPayload]
    scope_target_role_ids: list[UUID | None]
    created_at: datetime


class InterviewQuestionRequest(BaseModel):
    topic_id: UUID | None = None
    question: str
    category: str | None = None
    scope_target_role_ids: list[UUID | None]


class InterviewQuestionUpdateRequest(BaseModel):
    topic_id: UUID | None = None
    question: str
    category: str | None = None
    manual_answer: str | None = None
    reference_links: list[ReferenceLinkPayload] = []
    scope_target_role_ids: list[UUID | None]


class InterviewQuestionResponse(BaseModel):
    id: UUID
    topic_id: UUID | None
    question: str
    category: str | None
    manual_answer: str | None
    ai_answer: str | None
    ai_answer_status: str | None
    ai_answer_error: str | None
    ai_answer_generated_at: datetime | None
    reference_links: list[ReferenceLinkPayload]
    scope_target_role_ids: list[UUID | None]
    created_at: datetime


class InterviewPrepMoveRequest(BaseModel):
    """Move endpoints need the scope currently being viewed, not just a
    direction — reordering is independent per scope (the same item can
    sit at a different position in each scope's own list), so there's
    no longer a single implicit scope to derive from the item itself.
    Not the shared career_profile.schemas.MoveRequest, since that extra
    field is specific to this domain's multi-scope model."""

    direction: Literal["up", "down"]
    target_role_id: UUID | None = None


class InterviewPrepScopeSummaryResponse(BaseModel):
    target_role_id: UUID | None
    role_name: str
    topic_count: int
    question_count: int
