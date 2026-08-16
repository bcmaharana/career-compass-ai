"""Request/response schemas for the Interview Preparation API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReferenceLinkPayload(BaseModel):
    url: str
    label: str


class InterviewTopicRequest(BaseModel):
    target_role_id: UUID | None = None
    name: str
    section: str | None = None
    discussion: str | None = None


class InterviewTopicUpdateRequest(BaseModel):
    name: str
    section: str | None = None
    discussion: str | None = None
    reference_links: list[ReferenceLinkPayload] = []


class InterviewTopicResponse(BaseModel):
    id: UUID
    target_role_id: UUID | None
    name: str
    section: str | None
    discussion: str | None
    image_url: str | None
    reference_links: list[ReferenceLinkPayload]
    created_at: datetime


class InterviewQuestionRequest(BaseModel):
    target_role_id: UUID | None = None
    topic_id: UUID | None = None
    question: str


class InterviewQuestionUpdateRequest(BaseModel):
    topic_id: UUID | None = None
    question: str
    manual_answer: str | None = None
    reference_links: list[ReferenceLinkPayload] = []


class InterviewQuestionResponse(BaseModel):
    id: UUID
    target_role_id: UUID | None
    topic_id: UUID | None
    question: str
    manual_answer: str | None
    ai_answer: str | None
    ai_answer_status: str | None
    ai_answer_error: str | None
    ai_answer_generated_at: datetime | None
    reference_links: list[ReferenceLinkPayload]
    created_at: datetime


class InterviewPrepScopeSummaryResponse(BaseModel):
    target_role_id: UUID | None
    role_name: str
    topic_count: int
    question_count: int
