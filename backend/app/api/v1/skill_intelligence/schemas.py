"""Request/response schemas for the skill intelligence API (Phase 3,
simplified per ADR-005 — gap analysis only; My Skills and Target Role
Skill Requirements are plain free-text fields served by the career-profile
API, see app/api/v1/career_profile/schemas.py).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TargetRoleGapResponse(BaseModel):
    target_role_id: UUID
    role_name: str
    tag: str
    missing_skills: list[str]


class GapAnalysisResponse(BaseModel):
    target_role_gaps: list[TargetRoleGapResponse]
