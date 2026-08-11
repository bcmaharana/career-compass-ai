"""Unit tests for ResetPasswordService."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.application.identity.audit_service import AuditService
from app.application.identity.reset_password import ResetPasswordService
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_password, verify_password
from app.domain.identity.entities import AuditEvent, PasswordResetToken, User


class FakeTenantContextBinder:
    async def bind(self, tenant_id: uuid.UUID) -> None:
        return None


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def create(self, user: User) -> User:
        self.users[user.id] = replace(user)
        return replace(user)

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user and user.tenant_id == tenant_id else None

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        return None

    async def get_by_phone_e164(self, tenant_id: uuid.UUID, phone_e164: str) -> User | None:
        return None

    async def update(self, user: User) -> User:
        self.users[user.id] = replace(user)
        return replace(user)


class FakePasswordResetTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[uuid.UUID, PasswordResetToken] = {}

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        self.tokens[token.id] = replace(token)
        return replace(token)

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return replace(token)
        return None

    async def invalidate_unused_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        for token_id, token in self.tokens.items():
            if token.tenant_id == tenant_id and token.user_id == user_id and token.used_at is None:
                self.tokens[token_id] = replace(token, used_at=datetime.now(UTC))

    async def mark_used(self, token_id: uuid.UUID) -> None:
        token = self.tokens.get(token_id)
        if token is not None:
            self.tokens[token_id] = replace(token, used_at=datetime.now(UTC))


class FakeAuditEventRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def list_recent(self, tenant_id: uuid.UUID, *, limit: int = 50) -> list[AuditEvent]:
        return [e for e in self.events if e.tenant_id == tenant_id][:limit]


def _make_user(*, tenant_id: uuid.UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password=hash_password("old-password-123"),
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def _make_token(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, raw_token: str, expires_delta: timedelta, used: bool
) -> PasswordResetToken:
    now = datetime.now(UTC)
    return PasswordResetToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=now + expires_delta,
        used_at=now if used else None,
        created_at=now,
    )


_Setup = tuple[ResetPasswordService, FakeUserRepository, FakePasswordResetTokenRepository]


def _build() -> _Setup:
    users = FakeUserRepository()
    reset_tokens = FakePasswordResetTokenRepository()
    audit_events = FakeAuditEventRepository()

    service = ResetPasswordService(
        reset_tokens=reset_tokens,
        users=users,
        tenant_context=FakeTenantContextBinder(),
        audit=AuditService(audit_events),
    )
    return service, users, reset_tokens


@pytest.mark.unit
class TestResetPassword:
    async def test_valid_token_resets_the_password(self) -> None:
        service, users, reset_tokens = _build()
        user = _make_user(tenant_id=uuid.uuid4())
        await users.create(user)
        token = _make_token(
            tenant_id=user.tenant_id,
            user_id=user.id,
            raw_token="a-real-token",
            expires_delta=timedelta(minutes=30),
            used=False,
        )
        await reset_tokens.create(token)

        await service.execute(token="a-real-token", new_password="new-password-456")

        stored = users.users[user.id]
        assert verify_password("new-password-456", stored.hashed_password)
        assert not verify_password("old-password-123", stored.hashed_password)
        assert reset_tokens.tokens[token.id].used_at is not None

    async def test_expired_token_is_rejected(self) -> None:
        service, users, reset_tokens = _build()
        user = _make_user(tenant_id=uuid.uuid4())
        await users.create(user)
        token = _make_token(
            tenant_id=user.tenant_id,
            user_id=user.id,
            raw_token="expired-token",
            expires_delta=timedelta(minutes=-1),
            used=False,
        )
        await reset_tokens.create(token)

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="expired-token", new_password="new-password-456")

        assert exc_info.value.code == "INVALID_RESET_TOKEN"

    async def test_already_used_token_is_rejected(self) -> None:
        service, users, reset_tokens = _build()
        user = _make_user(tenant_id=uuid.uuid4())
        await users.create(user)
        token = _make_token(
            tenant_id=user.tenant_id,
            user_id=user.id,
            raw_token="used-token",
            expires_delta=timedelta(minutes=30),
            used=True,
        )
        await reset_tokens.create(token)

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="used-token", new_password="new-password-456")

        assert exc_info.value.code == "INVALID_RESET_TOKEN"

    async def test_unknown_token_is_rejected(self) -> None:
        service, _, _ = _build()

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="never-issued", new_password="new-password-456")

        assert exc_info.value.code == "INVALID_RESET_TOKEN"

    async def test_token_cannot_be_reused_after_a_successful_reset(self) -> None:
        service, users, reset_tokens = _build()
        user = _make_user(tenant_id=uuid.uuid4())
        await users.create(user)
        token = _make_token(
            tenant_id=user.tenant_id,
            user_id=user.id,
            raw_token="one-shot-token",
            expires_delta=timedelta(minutes=30),
            used=False,
        )
        await reset_tokens.create(token)

        await service.execute(token="one-shot-token", new_password="new-password-456")

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="one-shot-token", new_password="another-password-789")

        assert exc_info.value.code == "INVALID_RESET_TOKEN"
