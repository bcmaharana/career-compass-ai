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
#: Groq's free tier enforces a hard ~12000-token-per-request cap (see
#: groq_provider.py's _SAFE_TOTAL_TOKEN_BUDGET) that this app has no
#: control over — the adapter can clamp its OWN max_tokens ask down to
#: fit, but has no way to shrink an already-oversized INPUT prompt.
#: _MAX_HISTORY_MESSAGES alone doesn't bound total size, since
#: individual messages (especially AI replies, which can run several
#: thousand characters) vary wildly in length — a real 30-message
#: conversation with several ~3500-char replies exceeded Groq's cap and
#: fell back to the generic "trouble reaching the AI" message until this
#: was added (caught from a direct user report, 2026-08-21). Trimming by
#: a character budget on top of the message-count cap keeps the
#: rendered history a safe size regardless of how verbose past replies
#: were.
_MAX_HISTORY_CHARS = 20000

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

    async def get_latest_conversation_id(
        self, *, tenant_id: UUID, user_id: UUID
    ) -> UUID | None:
        """Lets the frontend resume the same conversation after a full
        page reload or a logout/login cycle — chat-store.ts holds
        conversation_id only in memory (deliberately, so a stray tab
        doesn't leak one user's conversation into a different session on
        the same browser), so without this, every reload started a
        brand-new, historyless conversation even though the old one and
        its messages were still sitting in the database the whole time.
        """
        conversation = await self._conversations.get_latest_for_user(tenant_id, user_id)
        return conversation.id if conversation else None

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID
    ) -> ChatConversation:
        conversation = await self._conversations.get_by_id(tenant_id, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise NotFoundError(
                "Chat conversation not found.", code="CHAT_CONVERSATION_NOT_FOUND"
            )
        return conversation

    async def list_messages(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID
    ) -> list[ChatMessage]:
        """Real, fetchable history — added 2026-08-21 alongside the
        delete/clear actions below (direct request: "keeping the
        conversation should be same as JD Tailoring") so the AI Career
        Coach conversation can be redisplayed in full whenever it's
        shown, the same way JdTailoringSessionService.list_messages
        already works, instead of only ever accumulating in the
        frontend's in-memory chat-store as messages are sent this
        session."""
        await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )
        return await self._messages.list_by_conversation(tenant_id, conversation_id)

    async def clear_messages(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID
    ) -> None:
        """Wipes just the conversation — the conversation row itself
        stays, so the same conversation_id keeps being reused for the
        next message rather than starting a brand-new one. Mirrors
        JdTailoringSessionService.clear_messages exactly (direct request
        for consistency across every AI conversation surface)."""
        await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )
        await self._messages.delete_all_for_conversation(tenant_id, conversation_id)

    async def delete_conversation(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID
    ) -> None:
        """Removes the conversation entirely — unlike clear_messages,
        the next message this user sends starts a genuinely new
        conversation (get_latest_conversation_id finds nothing to
        resume). Messages are deleted first since there's no ON DELETE
        CASCADE on the FK (same explicit-ordering convention as
        SqlAlchemyAccountDeletionRepository)."""
        await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )
        await self._messages.delete_all_for_conversation(tenant_id, conversation_id)
        await self._conversations.delete(tenant_id, conversation_id)

    async def delete_message(
        self, *, tenant_id: UUID, user_id: UUID, conversation_id: UUID, message_id: UUID
    ) -> list[UUID]:
        """Removes a whole question+answer turn — the message targeted
        plus its paired counterpart, if one sits immediately adjacent to
        it in conversation order. Identical pairing logic to
        JdTailoringSessionService.delete_message (direct request for
        consistency); see that method's docstring for the full
        reasoning. Returns every id actually removed, same reason the
        JD Tailoring endpoint does — so the caller's cache update can
        remove every affected bubble, not just the one it clicked."""
        await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )
        history = await self._messages.list_by_conversation(tenant_id, conversation_id)
        target_index = next((i for i, m in enumerate(history) if m.id == message_id), None)

        ids_to_delete = [message_id]
        if target_index is not None:
            target = history[target_index]
            if target.role == ChatMessageRole.USER:
                paired = history[target_index + 1] if target_index + 1 < len(history) else None
                if paired is not None and paired.role == ChatMessageRole.ASSISTANT:
                    ids_to_delete.append(paired.id)
            elif target.role == ChatMessageRole.ASSISTANT:
                paired = history[target_index - 1] if target_index > 0 else None
                if paired is not None and paired.role == ChatMessageRole.USER:
                    ids_to_delete.append(paired.id)

        for id_to_delete in ids_to_delete:
            await self._messages.delete(tenant_id, conversation_id, id_to_delete)
        return ids_to_delete

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

        existing_conversation = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation_id
        )
        return existing_conversation.id


def _render_history(history: list[ChatMessage]) -> str:
    if not history:
        return "(no previous messages)"

    recent = history[-_MAX_HISTORY_MESSAGES:]
    speaker = {ChatMessageRole.USER: "User", ChatMessageRole.ASSISTANT: "Assistant"}
    lines = [f"{speaker[message.role]}: {message.content}" for message in recent]

    # Drop the oldest lines first until the rendered history fits the
    # character budget — see _MAX_HISTORY_CHARS above for why a
    # message-count cap alone isn't enough. Always keeps at least the
    # single most recent line, even if it alone exceeds the budget.
    while len(lines) > 1 and sum(len(line) for line in lines) > _MAX_HISTORY_CHARS:
        lines.pop(0)

    return "\n".join(lines)
