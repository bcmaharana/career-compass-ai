"""Request/response schemas for the career profile API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class CareerProfileResponse(BaseModel):
    id: UUID
    current_version: int
    headline: str | None
    summary: str | None
    career_readiness_score: int | None
    photo_url: str | None
    core_competencies: list[str]
    section_order: list[str] | None


class UpdateCareerProfileRequest(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=10_000)
    core_competencies: list[str] | None = Field(default=None, max_length=50)
    section_order: list[str] | None = Field(default=None, max_length=20)


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


class ExperienceResponse(BaseModel):
    id: UUID
    title: str
    company: str
    location: str | None
    start_date: date
    end_date: date | None
    description: str | None
    display_order: int


class EducationRequest(BaseModel):
    institution: str = Field(min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=5_000)


class EducationResponse(BaseModel):
    id: UUID
    institution: str
    degree: str | None
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    description: str | None
    display_order: int


class CertificationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    issuing_organization: str = Field(min_length=1, max_length=255)
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=255)
    credential_url: str | None = Field(default=None, max_length=2048)


class CertificationResponse(BaseModel):
    id: UUID
    name: str
    issuing_organization: str
    issue_date: date | None
    expiration_date: date | None
    credential_id: str | None
    credential_url: str | None
    display_order: int


class CareerGoalRequest(BaseModel):
    target_role: str = Field(min_length=1, max_length=255)
    target_date: date | None = None
    description: str | None = Field(default=None, max_length=2_000)


class CareerGoalUpdateRequest(CareerGoalRequest):
    status: str = Field(pattern="^(active|achieved|abandoned)$")


class CareerGoalResponse(BaseModel):
    id: UUID
    target_role: str
    target_date: date | None
    status: str
    description: str | None
    display_order: int


class CareerHighlightRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    occurred_on: date | None = None


class CareerHighlightResponse(BaseModel):
    id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int


class KeyAchievementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    occurred_on: date | None = None


class KeyAchievementResponse(BaseModel):
    id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int


class PeerEndorsementRequest(BaseModel):
    recommender_name: str = Field(min_length=1, max_length=255)
    recommender_title: str | None = Field(default=None, max_length=255)
    relationship: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=5_000)


class PeerEndorsementResponse(BaseModel):
    id: UUID
    recommender_name: str
    recommender_title: str | None
    relationship: str | None
    content: str
    display_order: int


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
