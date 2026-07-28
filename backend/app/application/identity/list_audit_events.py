"""List recent audit events for the caller's tenant.

Authorization (does the caller hold "audit_event:read"?) is enforced at
the API layer via the require_permission dependency, not here — this
service assumes the caller is already authorized and simply fetches data.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.identity.entities import AuditEvent
from app.domain.identity.repositories import AuditEventRepository


class ListAuditEventsService:
    def __init__(self, audit_events: AuditEventRepository) -> None:
        self._audit_events = audit_events

    async def execute(self, *, tenant_id: UUID, limit: int = 50) -> list[AuditEvent]:
        return await self._audit_events.list_recent(tenant_id, limit=limit)
