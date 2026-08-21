"""Unit tests for ChatService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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

    async def get_latest_for_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> ChatConversation | None:
        matches = [
            c
            for c in self.conversations.values()
            if c.tenant_id == tenant_id and c.user_id == user_id
        ]
        return max(matches, key=lambda c: c.created_at) if matches else None

    async def delete(self, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        conversation = self.conversations.get(conversation_id)
        if conversation is not None and conversation.tenant_id == tenant_id:
            del self.conversations[conversation_id]


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

    async def delete_all_for_conversation(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        self.messages = [
            m
            for m in self.messages
            if not (m.tenant_id == tenant_id and m.conversation_id == conversation_id)
        ]

    async def delete(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> None:
        self.messages = [
            m
            for m in self.messages
            if not (
                m.tenant_id == tenant_id
                and m.conversation_id == conversation_id
                and m.id == message_id
            )
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

    async def test_history_is_trimmed_by_character_budget_not_just_message_count(
        self, service
    ) -> None:
        # 2026-08-21: a real 30-message conversation with several
        # ~3500-char AI replies exceeded Groq's per-request token cap —
        # the message-count cap (_MAX_HISTORY_MESSAGES=20) alone doesn't
        # bound total rendered size. Seeds several large messages
        # directly (bypassing send_message, which would each trigger a
        # real LLM call) to simulate that shape without needing 20+
        # real turns.
        svc, conversations, messages, llm = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        conversation = await conversations.create(
            ChatConversation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                created_at=datetime.now(UTC),
            )
        )
        for i in range(10):
            await messages.create(
                ChatMessage(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    conversation_id=conversation.id,
                    role=ChatMessageRole.USER if i % 2 == 0 else ChatMessageRole.ASSISTANT,
                    content=f"Message {i}: " + ("x" * 3500),
                    created_at=datetime.now(UTC),
                )
            )

        await svc.send_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation.id,
            content="Latest question",
        )

        history = llm.calls[0]["input_variables"]["conversation_history"]
        assert len(history) <= 20000
        # The most recent seeded message survives the trim; the oldest
        # (Message 0) is dropped to make room.
        assert "Message 9" in history
        assert "Message 0" not in history

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


@pytest.mark.unit
class TestListMessages:
    async def test_returns_messages_in_chronological_order(self, service) -> None:
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

        messages = await svc.list_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=first.conversation_id
        )

        assert [m.content for m in messages] == ["Hello", llm.reply, "Follow-up", llm.reply]

    async def test_raises_not_found_for_another_users_conversation(self, service) -> None:
        svc, _, _, _ = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=owner, conversation_id=None, content="Hello"
        )

        with pytest.raises(NotFoundError):
            await svc.list_messages(
                tenant_id=tenant_id, user_id=other, conversation_id=turn.conversation_id
            )


@pytest.mark.unit
class TestClearMessages:
    async def test_removes_all_messages_but_keeps_the_conversation(self, service) -> None:
        svc, conversations, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        await svc.clear_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=turn.conversation_id
        )

        messages = await svc.list_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=turn.conversation_id
        )
        assert messages == []
        assert turn.conversation_id in conversations.conversations


@pytest.mark.unit
class TestDeleteConversation:
    async def test_removes_the_conversation_and_its_messages(self, service) -> None:
        svc, conversations, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        await svc.delete_conversation(
            tenant_id=tenant_id, user_id=user_id, conversation_id=turn.conversation_id
        )

        assert turn.conversation_id not in conversations.conversations
        assert await svc.get_latest_conversation_id(tenant_id=tenant_id, user_id=user_id) is None

    async def test_cannot_delete_another_users_conversation(self, service) -> None:
        svc, _, _, _ = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=owner, conversation_id=None, content="Hello"
        )

        with pytest.raises(NotFoundError):
            await svc.delete_conversation(
                tenant_id=tenant_id, user_id=other, conversation_id=turn.conversation_id
            )


@pytest.mark.unit
class TestDeleteMessage:
    async def test_deleting_the_assistant_reply_also_deletes_its_question(self, service) -> None:
        svc, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        await svc.delete_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=turn.conversation_id,
            message_id=turn.assistant_message.id,
        )

        messages = await svc.list_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=turn.conversation_id
        )
        assert messages == []

    async def test_deleting_the_question_also_deletes_its_assistant_reply(self, service) -> None:
        svc, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        await svc.delete_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=turn.conversation_id,
            message_id=turn.user_message.id,
        )

        messages = await svc.list_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=turn.conversation_id
        )
        assert messages == []

    async def test_a_lone_message_with_no_adjacent_pair_deletes_just_itself(
        self, service
    ) -> None:
        svc, conversations, messages, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        conversation = await conversations.create(
            ChatConversation(
                id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id, created_at=datetime.now(UTC)
            )
        )
        lone = await messages.create(
            ChatMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                role=ChatMessageRole.USER,
                content="Still waiting on a reply",
                created_at=datetime.now(UTC),
            )
        )

        await svc.delete_message(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation.id,
            message_id=lone.id,
        )

        remaining = await svc.list_messages(
            tenant_id=tenant_id, user_id=user_id, conversation_id=conversation.id
        )
        assert remaining == []
