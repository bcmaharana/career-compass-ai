"""Unit tests for HandleService — fake repository, no database."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.handle_service import HandleAssignmentFailedError, HandleService
from app.core.exceptions import NotFoundError
from app.domain.identity.entities import User

pytestmark = pytest.mark.unit


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self._taken_handles_lower: set[str] = set()

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user and user.tenant_id == tenant_id else None

    async def set_handle(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, handle: str) -> bool:
        if handle.lower() in self._taken_handles_lower:
            return False
        self._taken_handles_lower.add(handle.lower())
        self.users[user_id].handle = handle
        return True


def _make_user(
    *, tenant_id: uuid.UUID, first_name: str = "Bishnu", middle_name: str | None = "Chandra",
    last_name: str = "Maharana", handle: str | None = None,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="user@example.com",
        salutation=None,
        first_name=first_name,
        last_name=last_name,
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
        middle_name=middle_name,
        handle=handle,
    )


class TestEnsureHandle:
    async def test_returns_the_existing_handle_unchanged(self) -> None:
        tenant_id = uuid.uuid4()
        repo = FakeUserRepository()
        user = _make_user(tenant_id=tenant_id, handle="ALREADYSET")
        repo.users[user.id] = user
        service = HandleService(repo)  # type: ignore[arg-type]

        handle = await service.ensure_handle(tenant_id=tenant_id, user_id=user.id)

        assert handle == "ALREADYSET"

    async def test_assigns_a_default_handle_from_initials(self) -> None:
        tenant_id = uuid.uuid4()
        repo = FakeUserRepository()
        user = _make_user(
            tenant_id=tenant_id, first_name="Bishnu", middle_name="Chandra", last_name="Maharana"
        )
        repo.users[user.id] = user
        service = HandleService(repo)  # type: ignore[arg-type]

        handle = await service.ensure_handle(tenant_id=tenant_id, user_id=user.id)

        assert handle == "BCM"
        assert repo.users[user.id].handle == "BCM"

    async def test_appends_a_numeric_suffix_on_collision(self) -> None:
        tenant_id = uuid.uuid4()
        repo = FakeUserRepository()
        repo._taken_handles_lower.add("bcm")
        user = _make_user(tenant_id=tenant_id)
        repo.users[user.id] = user
        service = HandleService(repo)  # type: ignore[arg-type]

        handle = await service.ensure_handle(tenant_id=tenant_id, user_id=user.id)

        assert handle == "BCM2"

    async def test_raises_after_exhausting_all_attempts(self) -> None:
        tenant_id = uuid.uuid4()
        repo = FakeUserRepository()
        repo._taken_handles_lower.add("bcm")
        for attempt in range(2, 51):
            repo._taken_handles_lower.add(f"bcm{attempt}".lower())
        user = _make_user(tenant_id=tenant_id)
        repo.users[user.id] = user
        service = HandleService(repo)  # type: ignore[arg-type]

        with pytest.raises(HandleAssignmentFailedError):
            await service.ensure_handle(tenant_id=tenant_id, user_id=user.id)

    async def test_raises_not_found_for_a_missing_user(self) -> None:
        tenant_id = uuid.uuid4()
        service = HandleService(FakeUserRepository())  # type: ignore[arg-type]

        with pytest.raises(NotFoundError):
            await service.ensure_handle(tenant_id=tenant_id, user_id=uuid.uuid4())
