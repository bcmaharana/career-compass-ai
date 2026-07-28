"""Chat domain entities (UI enhancement brief Part 1.2).

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/identity/entities.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ChatMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(slots=True)
class ChatConversation:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    created_at: datetime


@dataclass(slots=True)
class ChatMessage:
    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    role: ChatMessageRole
    content: str
    created_at: datetime
