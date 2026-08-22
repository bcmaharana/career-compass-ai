"""Lazily assigns a user's public-sharing handle the first time one is
actually needed (2026-08-22) — the moment they first make ANY resource
(a Showcase Page or an Interview Prep Topic/"Article") public, rather
than forcing everyone to visit Settings first. A user who already set
their own handle in Settings > Profile keeps it untouched.

Shared by ShowcasePageService.set_public and InterviewTopicService's
public-toggle so the same handle-assignment logic isn't duplicated per
resource type — both call PublicShareLinkService.get_or_create_key,
which calls this before minting a new share key.
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import CareerCompassError, NotFoundError
from app.domain.identity.handle import derive_default_handle_base
from app.domain.identity.repositories import UserRepository

#: A bounded retry loop, not an unbounded one — if 50 numeric-suffixed
#: variants of a 3-letter base are all somehow taken, something unusual
#: is going on (this app has nowhere near enough users for that to happen
#: organically), and surfacing a clear error beats looping forever.
_MAX_HANDLE_ATTEMPTS = 50


class HandleAssignmentFailedError(CareerCompassError):
    def __init__(self) -> None:
        super().__init__(
            "Could not assign a default sharing handle automatically — "
            "please set one in Settings > Profile.",
            code="HANDLE_ASSIGNMENT_FAILED",
        )


class HandleService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def ensure_handle(self, *, tenant_id: UUID, user_id: UUID) -> str:
        user = await self._users.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        if user.handle:
            return user.handle

        base = derive_default_handle_base(user.first_name, user.middle_name, user.last_name)
        for attempt in range(_MAX_HANDLE_ATTEMPTS):
            candidate = base if attempt == 0 else f"{base}{attempt + 1}"
            if await self._users.set_handle(tenant_id=tenant_id, user_id=user_id, handle=candidate):
                return candidate
        raise HandleAssignmentFailedError()
