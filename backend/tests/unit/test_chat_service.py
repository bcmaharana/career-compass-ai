"""Unit tests for ChatService."""

from __future__ import annotations

import uuid

import pytest

from app.application.chat.chat_service import ChatService
from app.core.exceptions import NotFoundError
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


@pytest.fixture
def service() -> tuple[ChatService, FakeChatConversationRepository, FakeChatMessageRepository]:
    conversations = FakeChatConversationRepository()
    messages = FakeChatMessageRepository()
    return ChatService(conversations, messages), conversations, messages


@pytest.mark.unit
class TestSendMessage:
    async def test_first_message_creates_a_new_conversation(self, service) -> None:
        svc, conversations, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        turn = await svc.send_message(
            tenant_id=tenant_id, user_id=user_id, conversation_id=None, content="Hello"
        )

        assert turn.conversation_id in conversations.conversations
        assert turn.user_message.role is ChatMessageRole.USER
        assert turn.user_message.content == "Hello"
        assert turn.assistant_message.role is ChatMessageRole.ASSISTANT

    async def test_second_message_reuses_the_given_conversation(self, service) -> None:
        svc, _, messages = service
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
        svc, _, _ = service
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
        svc, _, _ = service
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
