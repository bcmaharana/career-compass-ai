"""ORM models for platform administration.

Both tables are genuinely cross-tenant, so neither carries a RLS policy
— the same "no ENABLE/FORCE ROW LEVEL SECURITY, deliberate not an
oversight" shape as personal_phone_logins (app/adapters/db/models/identity.py):
a platform-admin permission check must be answerable for the caller's own
(tenant_id, user_id) without first needing tenant context bound, and
platform_settings is genuinely global configuration, not owned by any
tenant at all.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class PlatformAdminModel(Base):
    __tablename__ = "platform_admins"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_platform_admins_tenant_user"),
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
    # Snapshot at grant time, refreshed on every update — avoids a
    # cross-tenant users/tenants lookup just to render the admins list
    # (RLS would block that without already knowing this exact
    # tenant_id). subdomain lets the admins list tell apart two grants
    # for the same email under different tenants (e.g. Personal vs
    # Enterprise accounts sharing an email).
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(63), nullable=False)
    permission_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class PlatformSettingModel(Base):
    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
