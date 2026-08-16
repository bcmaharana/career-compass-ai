"""Learning Intelligence domain entities (Phase 7).

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/career_profile/entities.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

LearningItemStatus = str  # "planned" | "in_progress" | "completed"


@dataclass(slots=True)
class LearningItem:
    """A single self-managed learning log entry. Scoped directly by
    user_id (not career_profile_id) — same shape as CareerGoal, a flat
    per-user log rather than something tied to a Master/Target-Role
    Profile."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str
    provider: str | None
    url: str | None
    status: LearningItemStatus
    notes: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    #: Optional link to a TargetRole this item is meant to help close a
    #: skill gap for — nullable, ON DELETE SET NULL (deleting the target
    #: role shouldn't delete the learning history built against it).
    target_role_id: UUID | None = None
    started_at: date | None = None
    completed_at: date | None = None
    deleted_at: datetime | None = None


@dataclass(slots=True)
class LearningRecommendationSet:
    """One row per (tenant_id, user_id, target_role_id) — upserted in
    place on regenerate, never accumulates history (same idiom as
    ContentEmbeddingRepository.upsert's "re-embeds in place" docstring).
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role_id: UUID
    status: str  # "generated" | "failed"
    missing_skills_hash: str
    recommendations: list[dict[str, object]] | None
    error_message: str | None
    generated_at: datetime
