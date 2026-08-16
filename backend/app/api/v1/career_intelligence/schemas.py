"""Request/response schemas for the Career Intelligence Knowledge Graph
(CIKG) API.

Phase 4.5.1 MVP 2B: every per-entity-type `Create*Request` write schema
from MVP 1 is gone — all node/edge writes now go through the generic
`ProposeRevisionRequest`/`ContentRevisionResponse` pair below (see
ContentRevisionService). Read-side response schemas are unchanged.
`CreateSkillAliasRequest` is the one write schema that survives as-is —
`skill_alias` was never part of the governed-content system to begin
with.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SkillCategoryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    content_status: str


class CompetencyResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    content_status: str


class SkillResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    content_status: str
    ats_keywords: list[str]
    proficiency_level_definitions: dict[str, str] | None


class SkillDetailResponse(SkillResponse):
    category_ids: list[UUID]
    related_skill_ids: list[UUID]
    aliases: list[str]


class CikgRoleResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    experience_level: str | None
    content_status: str


class RequiredSkillResponse(BaseModel):
    skill_id: UUID
    requirement_level: str


class CikgRoleDetailResponse(CikgRoleResponse):
    required_skills: list[RequiredSkillResponse]


class CategoryParentResponse(BaseModel):
    id: UUID
    child_category_id: UUID
    parent_category_id: UUID
    content_status: str


class SkillCategoryMembershipResponse(BaseModel):
    id: UUID
    skill_id: UUID
    category_id: UUID
    content_status: str


class SkillCompetencyMembershipResponse(BaseModel):
    id: UUID
    skill_id: UUID
    competency_id: UUID
    content_status: str


class RelatedSkillResponse(BaseModel):
    id: UUID
    skill_a_id: UUID
    skill_b_id: UUID
    strength: str
    content_status: str


class RoleRequiredSkillResponse(BaseModel):
    id: UUID
    role_id: UUID
    skill_id: UUID
    requirement_level: str
    content_status: str


class SkillAliasResponse(BaseModel):
    id: UUID
    skill_id: UUID
    alias_text: str
    normalized_text: str
    source: str
    confidence: float | None


class CreateSkillAliasRequest(BaseModel):
    skill_id: UUID
    alias_text: str = Field(min_length=1, max_length=255)
    source: str = Field(pattern="^(curated|ai_suggested|user_confirmed)$")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ResolveAliasResponse(BaseModel):
    """`skill: null` is an expected, non-error outcome — see
    SkillAliasResolutionService's docstring."""

    skill: SkillResponse | None


class SearchResultResponse(BaseModel):
    entity_type: str
    entity_id: UUID
    name: str
    description: str | None
    score: float
    matched_via: list[str]


# --- Content governance (Phase 4.5.1 MVP 2B) ---

_ENTITY_TYPE_PATTERN = (
    "^(skill_category|competency|skill|cikg_role"
    "|edge:category_parent|edge:skill_category_membership"
    "|edge:skill_competency_membership|edge:related_to|edge:role_required_skill"
    "|edge:prerequisite_of|edge:specializes|edge:synonym_of|edge:role_progresses_to)$"
)


class ProposeRevisionRequest(BaseModel):
    entity_type: str = Field(pattern=_ENTITY_TYPE_PATTERN)
    entity_id: UUID | None = Field(
        default=None, description="Null proposes a brand-new entity; set to edit an existing one."
    )
    proposed_data: dict[str, object]
    source_attribution: str = Field(pattern="^(curated|ai_suggested|bulk_import)$")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    import_batch_id: UUID | None = None


class RejectRevisionRequest(BaseModel):
    review_notes: str = Field(min_length=1, max_length=2_000)


class BatchApproveRequest(BaseModel):
    import_batch_id: UUID


class ContentRevisionResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None
    proposed_data: dict[str, object]
    revision_number: int
    status: str
    confidence: float | None
    source_attribution: str
    import_batch_id: UUID | None
    reviewed_by: UUID | None
    review_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None


class FailedRevisionResponse(BaseModel):
    revision_id: UUID
    error: str


class BatchApprovalResultResponse(BaseModel):
    approved: list[UUID]
    failed: list[FailedRevisionResponse]
