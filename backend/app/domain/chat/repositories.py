"""Repository interfaces for the Chat bounded context.

Application services depend only on these Protocols — see
app/domain/identity/repositories.py for the established pattern this
follows.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.chat.entities import ChatConversation, ChatMessage


class ChatConversationRepository(Protocol):
    async def create(self, conversation: ChatConversation) -> ChatConversation: ...
    async def get_by_id(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> ChatConversation | None: ...
    async def get_latest_for_section(
        self, tenant_id: UUID, user_id: UUID, section_key: str
    ) -> ChatConversation | None:
        """Most recently *created* conversation for this user WITHIN this
        one section — not most recently active, and not across other
        sections (2026-08-22: conversations are scoped one-per-section,
        not one-per-account — see ChatConversation.section_key's own
        docstring for the real production issue that drove this). There's
        deliberately no "start a new conversation within a section"
        affordance, so a user has at most one conversation per section in
        practice, making "most recently created" vs. "most recently
        active" moot. Revisit (order by latest message instead) if a
        genuine multi-conversation-per-section UI ever ships."""
        ...
    async def delete(self, tenant_id: UUID, conversation_id: UUID) -> None:
        """Hard delete — no `deleted_at` column exists on this table, and
        this domain never needed one before this method. Caller must
        delete this conversation's messages first (no ON DELETE CASCADE
        on the FK), same explicit-ordering convention as
        SqlAlchemyAccountDeletionRepository."""
        ...


class ChatMessageRepository(Protocol):
    async def create(self, message: ChatMessage) -> ChatMessage: ...
    async def list_by_conversation(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> list[ChatMessage]:
        """Return the conversation's messages in chronological order —
        the context ChatService renders into the LLM prompt."""
        ...
    async def delete_all_for_conversation(self, tenant_id: UUID, conversation_id: UUID) -> None:
        """Wipes every message in the conversation — the conversation row
        itself is untouched (see ChatService.clear_messages)."""
        ...
    async def delete(self, tenant_id: UUID, conversation_id: UUID, message_id: UUID) -> None:
        """Removes exactly one message row — scoped by conversation_id
        too, so an id that doesn't actually belong to conversation_id
        matches zero rows and is a silent no-op."""
        ...
