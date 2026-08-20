"""SQLAlchemy ORM models for the JD Tailoring bounded context.

Both tables are tenant-owned (tenant_id NOT NULL, RLS with exact-match
policy — see the accompanying migration), same shape as
app/adapters/db/models/chat.py. jd_tailoring_messages has no
ON DELETE CASCADE from jd_tailoring_sessions — matches chat_messages'
own precedent — so account deletion cleans it up explicitly (see
app/adapters/db/account_deletion.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class JdTailoringSessionModel(Base):
    __tablename__ = "jd_tailoring_sessions"
    __table_args__ = (
        CheckConstraint("source_type IN ('job_listing', 'custom')", name="source_type"),
        CheckConstraint(
            "tailored_resume_status IS NULL OR tailored_resume_status IN ('generated', 'failed')",
            name="tailored_resume_status",
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
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_redirect_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    tailored_resume_docx_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tailored_resume_pdf_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tailored_resume_content: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    tailored_resume_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tailored_resume_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    tailored_resume_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JdTailoringMessageModel(Base):
    __tablename__ = "jd_tailoring_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jd_tailoring_sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
