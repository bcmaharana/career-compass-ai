"""Repository interfaces for the Resume Intelligence bounded context.

Application services depend only on this Protocol — see
app/domain/career_profile/repositories.py for the established pattern
this follows. A Resume row is write-once after creation (no update()/
move() — it isn't a list the user reorders).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.resume_intelligence.entities import Resume


class ResumeRepository(Protocol):
    async def create(self, resume: Resume) -> Resume: ...
    async def get_by_id(self, tenant_id: UUID, resume_id: UUID) -> Resume | None: ...
    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[Resume]:
        """Every non-deleted resume this user has uploaded, most recent
        first — a real history now (a person may keep multiple resume
        versions, each tailored to a different target role), not a
        single superseded slot."""
        ...
    async def soft_delete(self, tenant_id: UUID, resume_id: UUID) -> None: ...
