"""Request/response schemas for the career profile API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CoreCompetencyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    include_in_resume: bool = True


class CareerProfileResponse(BaseModel):
    id: UUID
    current_version: int
    headline: str | None
    summary: str | None
    career_readiness_score: int | None
    photo_url: str | None
    core_competencies: list[CoreCompetencyPayload]
    section_order: list[str] | None
    #: Freshly presigned each response (a stored URL would expire long
    #: before the profile is fetched again) — None if that format has
    #: never been generated for this profile. See ResumeExportService.
    resume_docx_url: str | None = None
    resume_pdf_url: str | None = None
    resume_generated_at: datetime | None = None
    #: Whole-section resume-inclusion toggles — see
    #: CareerProfile.resume_section_toggles for the key set/semantics.
    resume_section_toggles: dict[str, bool] | None = None


class GenerateResumeRequest(BaseModel):
    format: Literal["docx", "pdf"]


class CareerProfileSummaryResponse(BaseModel):
    """Cheap counts snapshot of one profile (Master or a Target Role
    Profile) — powers the frontend's Override-vs-Merge prompt during
    resume merge, so the choice is informed ("this profile already has 3
    experience entries and a summary") rather than a content-free yes/no.
    """

    experience_count: int
    education_count: int
    certification_count: int
    career_highlight_count: int
    key_achievement_count: int
    competency_count: int
    has_headline: bool
    has_summary: bool
    has_any_data: bool


class UpdateCareerProfileRequest(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=10_000)
    core_competencies: list[CoreCompetencyPayload] | None = Field(default=None, max_length=150)
    section_order: list[str] | None = Field(default=None, max_length=20)
    resume_section_toggles: dict[str, bool] | None = Field(default=None)


class MoveRequest(BaseModel):
    """Shared by every reorderable entity's move endpoint."""

    direction: str = Field(pattern="^(up|down)$")


class ExperienceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    start_date: date
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=5_000)
    include_in_resume: bool = True


class ExperienceResponse(BaseModel):
    id: UUID
    title: str
    company: str
    location: str | None
    start_date: date
    end_date: date | None
    description: str | None
    display_order: int
    include_in_resume: bool


class EducationRequest(BaseModel):
    institution: str = Field(min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=5_000)
    include_in_resume: bool = True


class EducationResponse(BaseModel):
    id: UUID
    institution: str
    degree: str | None
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    description: str | None
    display_order: int
    include_in_resume: bool


class CertificationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    issuing_organization: str = Field(min_length=1, max_length=255)
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=255)
    credential_url: str | None = Field(default=None, max_length=2048)
    include_in_resume: bool = True


class CertificationResponse(BaseModel):
    id: UUID
    name: str
    issuing_organization: str
    issue_date: date | None
    expiration_date: date | None
    credential_id: str | None
    credential_url: str | None
    display_order: int
    include_in_resume: bool


class CareerGoalRequest(BaseModel):
    target_role: str = Field(min_length=1, max_length=255)
    target_date: date | None = None
    description: str | None = Field(default=None, max_length=2_000)
    include_in_resume: bool = True


class CareerGoalUpdateRequest(CareerGoalRequest):
    status: str = Field(pattern="^(active|achieved|abandoned)$")


class CareerGoalResponse(BaseModel):
    id: UUID
    target_role: str
    target_date: date | None
    status: str
    description: str | None
    display_order: int
    include_in_resume: bool


class CareerHighlightRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    occurred_on: date | None = None
    include_in_resume: bool = True


class CareerHighlightResponse(BaseModel):
    id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int
    include_in_resume: bool


class KeyAchievementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    occurred_on: date | None = None
    include_in_resume: bool = True


class KeyAchievementResponse(BaseModel):
    id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int
    include_in_resume: bool


class PeerEndorsementRequest(BaseModel):
    recommender_name: str = Field(min_length=1, max_length=255)
    recommender_title: str | None = Field(default=None, max_length=255)
    relationship: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=5_000)
    include_in_resume: bool = True


class PeerEndorsementResponse(BaseModel):
    id: UUID
    recommender_name: str
    recommender_title: str | None
    relationship: str | None
    content: str
    display_order: int
    include_in_resume: bool


class PhotoUploadResponse(BaseModel):
    photo_url: str


class TargetRoleRequest(BaseModel):
    role_name: str = Field(min_length=1, max_length=255)
    tag: str = Field(min_length=1, max_length=3)


class TargetRoleResponse(BaseModel):
    id: UUID
    role_name: str
    tag: str
    required_skills: list[str]


class AddRequiredSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
