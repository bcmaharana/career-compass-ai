"""Request/response schemas for the JD Tailoring API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StartFromListingRequest(BaseModel):
    target_role_id: UUID | None = None
    provider_id: str
    title: str
    company: str
    redirect_url: str
    jd_text: str


class StartCustomRequest(BaseModel):
    target_role_id: UUID | None = None
    jd_text: str
    #: Resolved client-side (AI extraction + manual gap-fill) before this
    #: call — a custom session has no Adzuna listing to draw these from,
    #: but the auto-created Job Application needs them regardless of
    #: source (confirmed with the user).
    company: str
    role_title: str


class JdExtractionRequest(BaseModel):
    jd_text: str


class JdExtractionResponse(BaseModel):
    company: str | None
    role_title: str | None


class SendMessageRequest(BaseModel):
    content: str


class JdTailoringMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class JdTailoringSessionResponse(BaseModel):
    id: UUID
    target_role_id: UUID | None
    source_type: str
    source_title: str | None
    source_company: str | None
    source_redirect_url: str | None
    jd_text: str
    tailored_resume_status: str | None
    tailored_resume_error: str | None
    tailored_resume_generated_at: datetime | None
    tailored_resume_docx_url: str | None
    tailored_resume_pdf_url: str | None
    created_at: datetime


class StartSessionResponse(BaseModel):
    session: JdTailoringSessionResponse
    #: Always set — both entry points auto-create a linked Job Application.
    job_application_id: UUID


class SendMessageResponse(BaseModel):
    session_id: UUID
    user_message: JdTailoringMessageResponse
    assistant_message: JdTailoringMessageResponse
