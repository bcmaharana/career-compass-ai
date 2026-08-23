"""SQLAlchemy ORM models for the Showcase Page / public-sharing bounded
context.

ShowcasePageModel is tenant-owned (tenant_id NOT NULL, RLS with
exact-match policy — see the accompanying migration). PublicShareLinkModel
is deliberately NOT RLS-enabled — see the migration's module docstring
and app/domain/showcase_page/entities.py's PublicShareLink docstring for
why: an anonymous request must be able to resolve tenant_id from a bare
share_key before any tenant context can be bound.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class ShowcasePageModel(Base):
    __tablename__ = "showcase_pages"

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
        PG_UUID(as_uuid=True),
        ForeignKey("target_roles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # list[{"id": str, "type": str, "label": str, "html": str|None, ...}] —
    # the whole ordered block list as one JSON blob, replaced atomically on
    # every save (see app/domain/showcase_page/entities.py's module
    # docstring for why this isn't a separate child table).
    blocks: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    # Top-bar fields (2026-08-24) — seeded once from the owning User's
    # display_name and the resolved CareerProfile's headline/summary,
    # then independently editable (see ShowcasePage's own docstring).
    # No photo column here at all — the profile picture is deliberately
    # never copied/stored on this page, only ever resolved live.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublicShareLinkModel(Base):
    """RLS-exempt cross-tenant lookup — see this table's owning migration
    for the full rationale. Deliberately has no ORM relationship back to
    ShowcasePageModel/InterviewTopicModel (resource_type/resource_id is a
    plain polymorphic pointer, not a real FK, since it can point at either
    table)."""

    __tablename__ = "public_share_links"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('showcase_page', 'interview_topic')",
            name="ck_public_share_links_resource_type",
        ),
    )

    share_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
