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
    #: Which top-level Left Nav / mobile-tab-bar section this conversation
    #: belongs to (direct 2026-08-22 request: "the conversation was for
    #: that page only... not to be displayed in any other page") — the
    #: same `matchNavItem(pathname).to` value already used everywhere
    #: else in this app to identify a section (e.g. "/dashboard",
    #: "/profile", "/coach"). A conversation belongs to exactly one
    #: section for its whole lifetime; a user has at most one "current"
    #: conversation per section at a time (same "only one in practice"
    #: shape the single global conversation used to have, just now one
    #: per section instead of one per account). Existing conversations
    #: from before this field existed have "" here (a real migration
    #: default, not fabricated attribution) and are simply never resolved
    #: as any section's "latest" going forward — there's no way to know
    #: retroactively which section they belonged to.
    section_key: str = ""


@dataclass(slots=True)
class ChatMessage:
    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    role: ChatMessageRole
    content: str
    created_at: datetime
