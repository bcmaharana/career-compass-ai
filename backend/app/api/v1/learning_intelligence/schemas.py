"""Request/response schemas for the Learning Intelligence API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LearningItemRequest(BaseModel):
    title: str
    provider: str | None = None
    url: str | None = None
    target_role_id: UUID | None = None
    notes: str | None = None
    started_at: date | None = None


class LearningItemUpdateRequest(BaseModel):
    title: str
    provider: str | None = None
    url: str | None = None
    status: str = Field(pattern="^(planned|in_progress|completed)$")
    target_role_id: UUID | None = None
    notes: str | None = None
    started_at: date | None = None
    completed_at: date | None = None


class LearningItemResponse(BaseModel):
    id: UUID
    title: str
    provider: str | None
    url: str | None
    status: str
    target_role_id: UUID | None
    notes: str | None
    started_at: date | None
    completed_at: date | None
    created_at: datetime


class SkillRecommendationResponse(BaseModel):
    skill: str
    resources: list[str]
    summary: str


class LearningRecommendationResponse(BaseModel):
    target_role_id: UUID
    status: str
    generated_at: datetime
    recommendations: list[SkillRecommendationResponse] | None
    error_message: str | None
