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


class ChatMessageRepository(Protocol):
    async def create(self, message: ChatMessage) -> ChatMessage: ...
    async def list_by_conversation(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> list[ChatMessage]:
        """Return the conversation's messages in chronological order —
        the context ChatService renders into the LLM prompt."""
        ...
