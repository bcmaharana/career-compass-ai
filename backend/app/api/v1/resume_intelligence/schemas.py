"""Request/response schemas for the Resume Intelligence API.

ExtractedResumeData and its nested models give the LLM's JSON output a
typed shape at the API boundary — application code stores
extracted_data as a plain dict (app/domain/resume_intelligence/entities.py),
but the response schema here is what actually reaches the frontend and
what openapi-typescript codegens into TypeScript types.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractedExperience(BaseModel):
    title: str
    company: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class ExtractedEducation(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class ExtractedCertification(BaseModel):
    name: str
    issuing_organization: str
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    credential_url: str | None = None


class ExtractedCareerHighlight(BaseModel):
    title: str
    company: str | None = None
    description: str | None = None
    occurred_on: date | None = None


class ExtractedSkill(BaseModel):
    name: str
    category: str | None = None


class ExtractedResumeData(BaseModel):
    headline: str | None = None
    summary: str | None = None
    skills: list[ExtractedSkill] = Field(default_factory=list)
    experience: list[ExtractedExperience] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(default_factory=list)
    certifications: list[ExtractedCertification] = Field(default_factory=list)
    career_highlights: list[ExtractedCareerHighlight] = Field(default_factory=list)
    # Same shape as career_highlights (ExtractedCareerHighlight is reused
    # rather than a near-identical duplicate model) — a separate list
    # because they merge into a genuinely different Career Profile
    # section/table (Key Achievements, not Career Highlights). See the
    # extraction prompt's "career_highlights"/"key_achievements" field
    # guidance for how a resume line is routed into one or the other.
    key_achievements: list[ExtractedCareerHighlight] = Field(default_factory=list)


class ResumeResponse(BaseModel):
    id: UUID
    original_filename: str
    status: str
    extracted_data: ExtractedResumeData | None
    error_message: str | None
    target_role_id: UUID | None
    created_at: datetime


class ResumeSummary(BaseModel):
    """Lighter shape for the history list — omits extracted_data (can be
    a substantial JSON blob per resume) since the list view only needs
    to show filename/status/target role/date; the full detail is
    fetched separately (GET /resume-intelligence/{id}) when a specific
    resume is opened for review."""

    id: UUID
    original_filename: str
    status: str
    target_role_id: UUID | None
    created_at: datetime


class ResumeMergeRequest(BaseModel):
    resume_id: UUID
    # Which profile to merge into — required (not defaulted from the
    # resume's own stored tag) so the review screen can send the user's
    # explicit scope pick: None merges into Master, a real id into that
    # Target Role Profile. Deliberately independent of the resume's own
    # target_role_id (set once at upload time) so the same parsed resume
    # can be merged into a different profile than it was originally
    # tagged for, and merged again into additional profiles afterward —
    # see ResumeMergeService.merge()'s docstring.
    target_role_id: UUID | None
    accept_headline: bool = False
    accept_summary: bool = False
    accepted_skill_indices: list[int] = Field(default_factory=list, max_length=150)
    accepted_experience_indices: list[int] = Field(default_factory=list, max_length=100)
    accepted_education_indices: list[int] = Field(default_factory=list, max_length=100)
    accepted_certification_indices: list[int] = Field(default_factory=list, max_length=100)
    accepted_career_highlight_indices: list[int] = Field(default_factory=list, max_length=100)
    accepted_key_achievement_indices: list[int] = Field(default_factory=list, max_length=100)


class ResumeMergeResponse(BaseModel):
    added_experience_count: int
    added_education_count: int
    added_certification_count: int
    added_skills_count: int
    added_career_highlight_count: int
    added_key_achievement_count: int
    updated_headline: bool
    updated_summary: bool
    # Accepted experience entries that couldn't be added because no
    # usable start date was extracted for them (a required field) — the
    # rest of the merge still went through; the frontend surfaces these
    # so the user knows to add them manually instead.
    skipped_experience_titles: list[str] = Field(default_factory=list)
