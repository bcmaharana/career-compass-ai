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
    async def move(self, tenant_id: UUID, topic_id: UUID, direction: Direction) -> None: ...


class InterviewQuestionRepository(Protocol):
    async def create(self, question: InterviewQuestion) -> InterviewQuestion: ...
    async def get_by_id(self, tenant_id: UUID, question_id: UUID) -> InterviewQuestion | None: ...
    async def list_for_scope(
        self, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewQuestion]: ...
    async def update(self, question: InterviewQuestion) -> InterviewQuestion: ...
    async def soft_delete(self, tenant_id: UUID, question_id: UUID) -> None: ...
    async def move(self, tenant_id: UUID, question_id: UUID, direction: Direction) -> None: ...
