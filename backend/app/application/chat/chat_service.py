"""Chat application service (UI enhancement brief Part 1.2).

Scope for this round: the conversation/message thread and its
persistence are real, but the assistant's reply is a placeholder echo —
real AI reasoning arrives once the AI Platform is wired to a live
provider (see docs/architecture/ai-platform-architecture.md and
docs/adr/ADR-004-ai-governance-strategy.md, roughly Phase 4/8 territory).

A conversation is created lazily on its first message and continued by
passing the same conversation_id back on subsequent messages — ownership
follows the same not-found-not-forbidden reasoning as CareerGoalService.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.chat.entities import ChatConversation, ChatMessage, ChatMessageRole
from app.domain.chat.repositories import ChatConversationRepository, ChatMessageRepository


@dataclass(slots=True)
class ChatTurn:
    conversation_id: UUID
    user_message: ChatMessage
    assistant_message: ChatMessage


class ChatService:
    def __init__(
        self, conversations: ChatConversationRepository, messages: ChatMessageRepository
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def send_message(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        conversation_id: UUID | None,
        content: str,
    ) -> ChatTurn:
        conversation_id = await self._resolve_conversation_id(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )

        user_message = await self._messages.create(
            ChatMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=ChatMessageRole.USER,
                content=content,
                created_at=datetime.now(UTC),
            )
        )
        assistant_message = await self._messages.create(
            ChatMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=ChatMessageRole.ASSISTANT,
                content=_placeholder_reply(content),
                created_at=datetime.now(UTC),
            )
        )
        return ChatTurn(
            conversation_id=conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    async def _resolve_conversation_id(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID | None
    ) -> UUID:
        if conversation_id is None:
            conversation = await self._conversations.create(
                ChatConversation(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                )
            )
            return conversation.id

        existing_conversation = await self._conversations.get_by_id(tenant_id, conversation_id)
        if existing_conversation is None or existing_conversation.user_id != user_id:
            raise NotFoundError(
                "Chat conversation not found.", code="CHAT_CONVERSATION_NOT_FOUND"
            )
        return existing_conversation.id


def _placeholder_reply(content: str) -> str:
    return (
        "Thanks for the message — I'm not connected to a live AI model yet, "
        "so this is just an echo while the chat shell is being built: "
        f'"{content}"'
    )
