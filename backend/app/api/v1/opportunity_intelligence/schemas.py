"""Request/response schemas for the Opportunity Intelligence API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class JobListingResponse(BaseModel):
    provider_id: str
    title: str
    company: str | None
    location: str | None
    description: str
    redirect_url: str
    salary_min: float | None
    salary_max: float | None
    contract_type: str | None
    category: str | None
    posted_at: datetime | None


class JobListingsResponse(BaseModel):
    target_role_id: UUID
    role_query: str
    location_query: str
    fetched_at: datetime
    listings: list[JobListingResponse]


class CikgRoleSummary(BaseModel):
    id: UUID
    title: str
    description: str | None
    experience_level: str | None


class CareerPathResponse(BaseModel):
    resolved: bool
    matched_role: CikgRoleSummary | None
    match_type: str | None
    upstream: list[CikgRoleSummary]
    downstream: list[CikgRoleSummary]


class JobSearchPreferenceRequest(BaseModel):
    location: str | None = None
    max_days_old: Literal[1, 3, 7] | None = None
    distance_miles: Literal[10, 30, 50, 100] | None = None
    employment_time: Literal["full_time", "part_time"] | None = None
    employment_type: Literal["contract", "permanent"] | None = None


class JobSearchPreferenceResponse(BaseModel):
    location: str | None
    max_days_old: int | None
    distance_miles: int | None
    employment_time: str | None
    employment_type: str | None
