"""Audit service.

Thin wrapper application services call to record a business-meaningful
audit event. Kept separate from the AI Platform's InvocationLogger
(app/ai_platform/governance/invocation_logger.py) — that one tracks AI
invocations specifically; this one tracks user/admin/auth actions per
docs/architecture/security-architecture.md. AuditEvent rows are
append-only (enforced by a DB trigger — see the Phase 1 migration).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.domain.identity.entities import AuditEvent
from app.domain.identity.repositories import AuditEventRepository


class AuditService:
    def __init__(self, audit_events: AuditEventRepository) -> None:
        self._audit_events = audit_events

    async def record(
        self,
        *,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        user_id: UUID | None = None,
        resource_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=datetime.now(UTC),
            metadata=metadata or {},
            ip_address=ip_address,
        )
        return await self._audit_events.record(event)
