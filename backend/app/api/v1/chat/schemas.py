"""Request/response schemas for the chat API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SendChatMessageRequest(BaseModel):
    conversation_id: UUID | None = None
    content: str = Field(min_length=1, max_length=4_000)


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class SendChatMessageResponse(BaseModel):
    conversation_id: UUID
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class LatestConversationResponse(BaseModel):
    conversation_id: UUID | None


class DeleteChatMessageResponse(BaseModel):
    #: Every message row actually removed — the one the caller targeted
    #: plus its paired question/answer, if one was found adjacent to it
    #: (see ChatService.delete_message). Same shape/reasoning as JD
    #: Tailoring's identical DeleteMessageResponse — a bare 204 gives the
    #: frontend no way to know a second row also went, leaving that
    #: bubble stuck on screen until a full refetch.
    deleted_message_ids: list[UUID]
