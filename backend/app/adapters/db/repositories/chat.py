"""SQLAlchemy repository implementations for the Chat domain.

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/career_profile.py.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import ChatConversationModel, ChatMessageModel
from app.domain.chat.entities import ChatConversation, ChatMessage, ChatMessageRole


def _conversation_to_domain(model: ChatConversationModel) -> ChatConversation:
    return ChatConversation(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        created_at=model.created_at,
    )


def _message_to_domain(model: ChatMessageModel) -> ChatMessage:
    return ChatMessage(
        id=model.id,
        tenant_id=model.tenant_id,
        conversation_id=model.conversation_id,
        role=ChatMessageRole(model.role),
        content=model.content,
        created_at=model.created_at,
    )


class SqlAlchemyChatConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: ChatConversation) -> ChatConversation:
        model = ChatConversationModel(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _conversation_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, conversation_id: UUID) -> ChatConversation | None:
        result = await self._session.execute(
            select(ChatConversationModel).where(
                ChatConversationModel.tenant_id == tenant_id,
                ChatConversationModel.id == conversation_id,
            )
        )
        model = result.scalar_one_or_none()
        return _conversation_to_domain(model) if model else None

    async def get_latest_for_user(
        self, tenant_id: UUID, user_id: UUID
    ) -> ChatConversation | None:
        result = await self._session.execute(
            select(ChatConversationModel)
            .where(
                ChatConversationModel.tenant_id == tenant_id,
                ChatConversationModel.user_id == user_id,
            )
            .order_by(desc(ChatConversationModel.created_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _conversation_to_domain(model) if model else None


class SqlAlchemyChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: ChatMessage) -> ChatMessage:
        model = ChatMessageModel(
            id=message.id,
            tenant_id=message.tenant_id,
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _message_to_domain(model)

    async def list_by_conversation(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessageModel)
            .where(
                ChatMessageModel.tenant_id == tenant_id,
                ChatMessageModel.conversation_id == conversation_id,
            )
            .order_by(ChatMessageModel.created_at)
        )
        return [_message_to_domain(model) for model in result.scalars().all()]
