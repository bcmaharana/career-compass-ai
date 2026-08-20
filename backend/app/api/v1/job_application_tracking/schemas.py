"""Request/response schemas for the Job Application Tracking API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

_STATUS_PATTERN = (
    "^(considering|applied|phone_screen|interview|offer|rejected|withdrawn|"
    "didnt_hear_back|other)$"
)


class JobApplicationRequest(BaseModel):
    company: str
    role_title: str
    target_role_id: UUID | None = None
    status: str = Field(default="considering", pattern=_STATUS_PATTERN)
    applied_at: date | None = None
    notes: str | None = None
    recruiter_id: UUID | None = None


class JobApplicationUpdateRequest(BaseModel):
    company: str
    role_title: str
    status: str = Field(pattern=_STATUS_PATTERN)
    target_role_id: UUID | None = None
    applied_at: date | None = None
    notes: str | None = None
    recruiter_id: UUID | None = None


class InterviewRoundRequest(BaseModel):
    stage_label: str
    round_date: date | None = None
    interviewer_name: str | None = None
    interviewer_title: str | None = None
    notes: str | None = None


class InterviewRoundResponse(BaseModel):
    id: UUID
    job_application_id: UUID
    stage_label: str
    round_date: date | None
    interviewer_name: str | None
    interviewer_title: str | None
    notes: str | None
    display_order: int


class JobApplicationResponse(BaseModel):
    id: UUID
    company: str
    role_title: str
    status: str
    status_changed_at: datetime
    target_role_id: UUID | None
    source_title: str | None
    source_company: str | None
    source_redirect_url: str | None
    jd_tailoring_session_id: UUID | None
    recruiter_id: UUID | None
    applied_at: date | None
    notes: str | None
    interview_rounds: list[InterviewRoundResponse]
    created_at: datetime
    updated_at: datetime


class StatusCountResponse(BaseModel):
    status: str
    count: int


class NextInterviewResponse(BaseModel):
    application_id: UUID
    company: str
    role_title: str
    stage_label: str
    round_date: date


class StuckApplicationResponse(BaseModel):
    application_id: UUID
    company: str
    role_title: str
    status: str
    days_in_status: int


class JobApplicationSummaryResponse(BaseModel):
    status_counts: list[StatusCountResponse]
    next_interview: NextInterviewResponse | None
    stuck_count: int
    stuck_examples: list[StuckApplicationResponse]
