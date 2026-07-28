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
