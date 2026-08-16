"""SQLAlchemy ORM models for the Interview Preparation bounded context.
Both tables are tenant-owned (tenant_id NOT NULL, RLS with exact-match
policy — see the accompanying migration), same shape as
app/adapters/db/models/learning_intelligence.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class InterviewTopicModel(Base):
    """A study-notes card — scoped directly by user_id, optionally tied
    to a Target Role (target_role_id), same Master-vs-Target-Role split
    CareerProfileModel uses."""

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
    # ON DELETE SET NULL — deleting the target role shouldn't destroy
    # prep content, only unlink it back to generic/Master scope. Same
    # precedent as LearningItemModel.target_role_id.
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discussion: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # list[{"url": str, "label": str}] — same "nested value type inside a
    # JSON blob" pattern InterviewQuestionModel.reference_links uses.
    reference_links: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewQuestionModel(Base):
    """An interview question — scoped directly by user_id, optionally
    tied to a Target Role and/or an InterviewTopic."""

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
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("target_roles.id", ondelete="SET NULL"), nullable=True
    )
    # ON DELETE SET NULL — deleting a Topic un-links its questions
    # rather than deleting them.
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interview_topics.id", ondelete="SET NULL"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
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
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
