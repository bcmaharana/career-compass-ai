"""Unit tests for ChatService."""

from __future__ import annotations

import uuid

import pytest

from app.application.chat.chat_service import _FALLBACK_REPLY, ChatService
from app.core.exceptions import CareerCompassError, NotFoundError
from app.domain.chat.entities import ChatConversation, ChatMessage, ChatMessageRole


class FakeChatConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, ChatConversation] = {}

    async def create(self, conversation: ChatConversation) -> ChatConversation:
        self.conversations[conversation.id] = conversation
        return conversation

    async def get_by_id(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> ChatConversation | None:
        conversation = self.conversations.get(conversation_id)
        return conversation if conversation and conversation.tenant_id == tenant_id else None


class FakeChatMessageRepository:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    async def create(self, message: ChatMessage) -> ChatMessage:
        self.messages.append(message)
        return message

    async def list_by_conversation(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[ChatMessage]:
        return [
            m
            for m in self.messages
            if m.tenant_id == tenant_id and m.conversation_id == conversation_id
        ]


class FakeLLMService:
    """Records every call so tests can assert on the rendered prompt
    variables (conversation history, latest message) the service built."""

    def __init__(self, *, reply: str = "Great question — here's my advice.") -> None:
        self.reply = reply
        self.calls: list[dict] = []
        self.raises: Exception | None = None

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        max_tokens: int = 1000,
    ) -> str:
        self.calls.append(
            {
                "use_case": use_case,
                "input_variables": input_variables,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "max_tokens": max_tokens,
            }
        )
        if self.raises is not None:
            raise self.raises
        return self.reply


@pytest.fixture
def service() -> tuple[
    ChatService, FakeChatConversationRepository, FakeChatMessageRepository, FakeLLMService
]:
    conversations = FakeChatConversationRepository()
    messages = FakeChatMessageRepository()
    llm = FakeLLMService()
    return ChatService(conversations, messages, llm), conversations, messages, llm


@pytest.mark.unit
class TestSendMessage:
    async def test_first_message_creates_a_new_conversation(self, service) -> None:
        svc, conversations, _, llm = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        assert turn.conversation_id in conversations.conversations
        assert turn.user_message.role is ChatMessageRole.USER
        assert turn.user_message.content == "Hello"
        assert turn.assistant_message.role is ChatMessageRole.ASSISTANT
        assert turn.assistant_message.content == llm.reply

    async def test_second_message_reuses_the_given_conversation(self, service) -> None:
        svc, _, messages, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )
        second = await svc.send_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=first.conversation_id,
            content="Follow-up",
        )

        assert second.conversation_id == first.conversation_id
        assert len(messages.messages) == 4

    async def test_a_user_cannot_post_into_another_users_conversation(self, service) -> None:
        svc, _, _, _ = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()

        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=owner, conversation_id=None, content="Hello"
        )

        with pytest.raises(NotFoundError) as exc_info:
            await svc.send_message(
                tenant_id=tenant_id,
                user_id=intruder,
                conversation_id=turn.conversation_id,
                content="Hijack",
            )

        assert exc_info.value.code == "CHAT_CONVERSATION_NOT_FOUND"

    async def test_a_conversation_from_another_tenant_is_not_found(self, service) -> None:
        svc, _, _, _ = service
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        user_id = uuid.uuid4()

        turn = await svc.send_message(
            tenant_id=tenant_a, user_id=user_id, conversation_id=None, content="Hello"
        )

        with pytest.raises(NotFoundError):
            await svc.send_message(
                tenant_id=tenant_b,
                user_id=user_id,
                conversation_id=turn.conversation_id,
                content="Cross-tenant",
            )

    async def test_llm_is_called_with_use_case_and_rendered_variables(self, service) -> None:
        svc, _, _, llm = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        await svc.send_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=None,
            content="How do I negotiate?",
        )

        assert len(llm.calls) == 1
        call = llm.calls[0]
        assert call["use_case"] == "career_coach_chat"
        assert call["tenant_id"] == tenant_id
        assert call["user_id"] == user_id
        assert call["input_variables"]["user_message"] == "How do I negotiate?"
        assert call["input_variables"]["conversation_history"] == "(no previous messages)"

    async def test_second_turn_includes_prior_messages_as_history(self, service) -> None:
        svc, _, _, llm = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )
        await svc.send_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=first.conversation_id,
            content="Follow-up",
        )

        history = llm.calls[1]["input_variables"]["conversation_history"]
        assert "User: Hello" in history
        assert f"Assistant: {llm.reply}" in history

    async def test_llm_failure_falls_back_to_a_friendly_message_without_raising(
        self, service
    ) -> None:
        svc, _, _, llm = service
        llm.raises = CareerCompassError("boom", code="AI_PROVIDER_ERROR")
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        assert turn.assistant_message.content == _FALLBACK_REPLY
