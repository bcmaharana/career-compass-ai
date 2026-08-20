"""Repository interfaces for the JD Tailoring bounded context.

Application services depend only on these Protocols — see
app/domain/chat/repositories.py for the established pattern this
follows.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.jd_tailoring.entities import JdTailoringMessage, JdTailoringSession


class JdTailoringSessionRepository(Protocol):
    async def create(self, session: JdTailoringSession) -> JdTailoringSession: ...
    async def get_by_id(
        self, tenant_id: UUID, session_id: UUID
    ) -> JdTailoringSession | None: ...
    async def get_by_source_provider_id(
        self, tenant_id: UUID, user_id: UUID, provider_id: str
    ) -> JdTailoringSession | None:
        """Most recent non-deleted session started from this exact
        listing, if any — used by JdTailoringIntakeService to decide
        whether re-evaluating an already-tracked listing should reuse
        an existing application's link (it doesn't repoint it; see that
        service's own docstring)."""
        ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JdTailoringSession]:
        """Most recently created first — the session history list."""
        ...
    async def update(self, session: JdTailoringSession) -> JdTailoringSession: ...
    async def soft_delete(self, tenant_id: UUID, session_id: UUID) -> None: ...


class JdTailoringMessageRepository(Protocol):
    async def create(self, message: JdTailoringMessage) -> JdTailoringMessage: ...
    async def list_by_session(
        self, tenant_id: UUID, session_id: UUID
    ) -> list[JdTailoringMessage]:
        """Chronological order — the context rendered into the LLM
        prompt, same role ChatMessageRepository.list_by_conversation
        plays for the single-conversation Chat domain."""
        ...
    async def delete_all_for_session(self, tenant_id: UUID, session_id: UUID) -> None:
        """Wipes every message for one session — the session row itself
        is untouched, only its conversation history. A genuine hard
        delete (this table has no deleted_at column), used by
        JdTailoringSessionService.clear_messages."""
        ...

    async def delete(self, tenant_id: UUID, session_id: UUID, message_id: UUID) -> None:
        """Removes exactly one message — everything else in the
        conversation (and the session itself) is untouched. Scoped by
        both tenant_id and session_id (not just message_id) so a
        mismatched session_id in the request can never delete a message
        that actually belongs to a different session. Used by
        JdTailoringSessionService.delete_message. A genuine hard delete,
        same reasoning as delete_all_for_session above."""
        ...
