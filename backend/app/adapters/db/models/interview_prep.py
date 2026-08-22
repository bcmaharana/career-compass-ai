"""SQLAlchemy ORM models for the Interview Preparation bounded context.
All four tables are tenant-owned (tenant_id NOT NULL, RLS with
exact-match policy — see the accompanying migrations), same shape as
app/adapters/db/models/learning_intelligence.py.

InterviewTopicModel/InterviewQuestionModel no longer carry a scoping
column themselves — scoping is a many-to-many relationship, tracked in
InterviewTopicScopeTagModel/InterviewQuestionScopeTagModel (see those
classes' own docstrings, and app/domain/interview_prep/entities.py's
module docstring for the full "why").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class InterviewTopicModel(Base):
    """A study-notes card — scoped by user_id plus zero or more entries
    in InterviewTopicScopeTagModel (Master and/or one or more Target
    Roles)."""

    __tablename__ = "interview_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # list[{"id": str, "columns": [{"id": str, "type": str, "label": str,
    # "html": str|None, "image_key": str|None, ...}]}] — same row/column
    # content-block shape as ShowcasePageModel.blocks (see
    # app/domain/content_blocks/entities.py), replacing the old fixed
    # discussion/image_key/reference_links columns (2026-08-24).
    blocks: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewTopicScopeTagModel(Base):
    """One row per scope an InterviewTopic is tagged into and visible
    under — `target_role_id` NULL means the Master/generic scope,
    matching the NULL-means-Master convention used elsewhere in this
    app. `display_order` lives here, not on InterviewTopicModel,
    because the same topic can sit at a different position in each
    scope's own list (confirmed with the user: reordering is
    independent per scope). `ON DELETE CASCADE` on both FKs — deleting
    the topic or the target role just removes this one tag row, never
    cascades further.

    Two partial unique indexes (not one plain UNIQUE(topic_id,
    target_role_id)) enforce "at most one tag per topic per scope,
    including Master" — Postgres treats every NULL as distinct in a
    normal unique constraint, which would otherwise silently allow
    duplicate Master tags for the same topic. See the accompanying
    migration for the actual index DDL (SQLAlchemy has no first-class
    partial-unique-index construct on the model itself)."""

    __tablename__ = "interview_topic_scope_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    # Denormalized from the parent topic — lets next_display_order()/
    # move() scope "this user's ordered list for this scope" without a
    # join, which matters especially for Master (target_role_id IS
    # NULL, no owning row of its own to key off of).
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interview_topics.id", ondelete="CASCADE"), nullable=False
    )
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id", ondelete="CASCADE"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewQuestionModel(Base):
    """An interview question — scoped by user_id plus zero or more
    entries in InterviewQuestionScopeTagModel, optionally tied to an
    InterviewTopic."""

    __tablename__ = "interview_questions"
    __table_args__ = (
        CheckConstraint(
            "ai_answer_status IS NULL OR ai_answer_status IN ('generated', 'failed')",
            name="ai_answer_status",
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
    # ON DELETE SET NULL — deleting a Topic un-links its questions
    # rather than deleting them.
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interview_topics.id", ondelete="SET NULL"), nullable=True
    )
    # Set only on a follow-up question — ON DELETE CASCADE, unlike
    # topic_id's SET NULL, since a follow-up has no independent meaning
    # once its parent is gone (contrast a Topic link, which is a loose
    # cross-reference). display_order is meaningful only when this is
    # set (ordering among siblings sharing the same parent — see
    # app/domain/interview_prep/entities.py's docstring); unused
    # (left at its default) for a top-level question, whose ordering
    # instead lives in InterviewQuestionScopeTagModel, per-scope.
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manual_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_answer_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_answer_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_answer_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # list[{"url": str, "label": str}] — same "nested value type inside a
    # JSON blob" pattern CareerProfileModel.core_competencies uses.
    reference_links: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewQuestionScopeTagModel(Base):
    """One row per scope an InterviewQuestion is tagged into — mirrors
    InterviewTopicScopeTagModel exactly, see that class's docstring for
    the full rationale."""

    __tablename__ = "interview_question_scope_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False
    )
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id", ondelete="CASCADE"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
