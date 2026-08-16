"""Repository interfaces for the Interview Preparation bounded context.

Application services depend only on these Protocols — see
app/domain/career_profile/repositories.py for the established pattern
this follows.
"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic

#: Declared locally, not imported from app.adapters.db.reorder — domain/
#: must have zero adapter imports. Same duplication precedent as
#: app/domain/career_profile/repositories.py's own Direction alias.
Direction = Literal["up", "down"]


class InterviewTopicRepository(Protocol):
    async def create(self, topic: InterviewTopic) -> InterviewTopic: ...
    async def get_by_id(self, tenant_id: UUID, topic_id: UUID) -> InterviewTopic | None: ...
    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewTopic]: ...
    async def update(self, topic: InterviewTopic) -> InterviewTopic: ...
    async def soft_delete(self, tenant_id: UUID, topic_id: UUID) -> None: ...
    #: Untags the topic from exactly one scope (deletes that one
    #: (topic, target_role_id) tag row) without touching the topic
    #: itself or its other tags — the "just this scope" half of the
    #: delete-everywhere-vs-just-this-scope choice InterviewTopicService
    #: exposes. Caller is responsible for ensuring at least one scope
    #: remains (or calling soft_delete instead if none would).
    async def remove_scope(
        self, tenant_id: UUID, topic_id: UUID, target_role_id: UUID | None
    ) -> None: ...
    #: `target_role_id` identifies *which* scope's ordered list to move
    #: the topic within (None = Master) — required now that ordering is
    #: independent per scope rather than a single column on the topic.
    async def move(
        self, tenant_id: UUID, topic_id: UUID, target_role_id: UUID | None, direction: Direction
    ) -> None: ...


class InterviewQuestionRepository(Protocol):
    async def create(self, question: InterviewQuestion) -> InterviewQuestion: ...
    async def get_by_id(self, tenant_id: UUID, question_id: UUID) -> InterviewQuestion | None: ...
    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewQuestion]: ...
    async def update(self, question: InterviewQuestion) -> InterviewQuestion: ...
    async def soft_delete(self, tenant_id: UUID, question_id: UUID) -> None: ...
    async def remove_scope(
        self, tenant_id: UUID, question_id: UUID, target_role_id: UUID | None
    ) -> None: ...
    async def move(
        self, tenant_id: UUID, question_id: UUID, target_role_id: UUID | None, direction: Direction
    ) -> None: ...
