"""Chat application service.

The conversation/message thread and its persistence are real; the
assistant reply is now a real AI Platform call (Phase 4 — see
docs/architecture/ai-platform-architecture.md and
docs/adr/ADR-004-ai-governance-strategy.md). The prompt template lives
in the "career_coach_chat" PromptVersion (versioned/approved, not an
inline string here — see app/ai_platform/prompts/registry.py); recent
conversation history is rendered into it so the assistant has context
beyond the single latest message.

A provider failure (no API key configured, rate limit, network error,
etc.) degrades to an apologetic message rather than a 500 — a chat
feature should never hard-fail the whole request over an upstream LLM
outage, and the conversation itself is still persisted either way.

A conversation is created lazily on its first message and continued by
passing the same conversation_id back on subsequent messages — ownership
follows the same not-found-not-forbidden reasoning as CareerGoalService.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.ai_platform.llm_service.service import LLMServiceInterface
from app.core.exceptions import CareerCompassError, NotFoundError
from app.core.logging import get_logger
from app.domain.chat.entities import ChatConversation, ChatMessage, ChatMessageRole
from app.domain.chat.repositories import ChatConversationRepository, ChatMessageRepository

logger = get_logger(__name__)

_CHAT_USE_CASE = "career_coach_chat"
_MAX_HISTORY_MESSAGES = 20
_MAX_RESPONSE_TOKENS = 1000

_FALLBACK_REPLY = (
    "I'm having trouble reaching the AI coach right now — please try again in a moment. "
    "Your message has been saved."
)


@dataclass(slots=True)
class ChatTurn:
    conversation_id: UUID
    user_message: ChatMessage
    assistant_message: ChatMessage


class ChatService:
    def __init__(
        self,
        conversations: ChatConversationRepository,
        messages: ChatMessageRepository,
        llm_service: LLMServiceInterface,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._llm = llm_service

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

        history = await self._messages.list_by_conversation(tenant_id, conversation_id)

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

        reply = await self._generate_reply(
            tenant_id=tenant_id, user_id=user_id, history=history, content=content
        )

        assistant_message = await self._messages.create(
            ChatMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role=ChatMessageRole.ASSISTANT,
                content=reply,
                created_at=datetime.now(UTC),
            )
        )
        return ChatTurn(
            conversation_id=conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    async def _generate_reply(
        self, *, tenant_id: UUID, user_id: UUID, history: list[ChatMessage], content: str
    ) -> str:
        try:
            return await self._llm.generate(
                use_case=_CHAT_USE_CASE,
                input_variables={
                    "conversation_history": _render_history(history),
                    "user_message": content,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
            )
        except CareerCompassError as exc:
            logger.warning("chat_llm_generate_failed", code=exc.code, error=str(exc))
            return _FALLBACK_REPLY

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


def _render_history(history: list[ChatMessage]) -> str:
    if not history:
        return "(no previous messages)"

    recent = history[-_MAX_HISTORY_MESSAGES:]
    speaker = {ChatMessageRole.USER: "User", ChatMessageRole.ASSISTANT: "Assistant"}
    return "\n".join(f"{speaker[message.role]}: {message.content}" for message in recent)
