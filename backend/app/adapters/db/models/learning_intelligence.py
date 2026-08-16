"""SQLAlchemy ORM models for the Learning Intelligence bounded context
(Phase 7). Both tables are tenant-owned (tenant_id NOT NULL, RLS with
exact-match policy — see the accompanying migration), same shape as
app/adapters/db/models/career_profile.py.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class LearningItemModel(Base):
    """A self-managed learning log entry — scoped directly by user_id
    (not career_profile_id), same shape as CareerGoalModel."""

    __tablename__ = "learning_items"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'completed')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # ON DELETE SET NULL — deleting the target role shouldn't delete the
    # learning history built against it, only unlink it.
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningRecommendationSetModel(Base):
    """One row per (tenant_id, user_id, target_role_id) — upserted in
    place on regenerate, never accumulates history."""

    __tablename__ = "learning_recommendation_sets"
    __table_args__ = (
        CheckConstraint("status IN ('generated', 'failed')", name="status"),
        UniqueConstraint(
            "tenant_id", "user_id", "target_role_id", name="uq_learning_recommendation_sets_scope"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    target_role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    missing_skills_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    recommendations: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
