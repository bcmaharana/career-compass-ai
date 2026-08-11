"""Unit tests for RequestPasswordResetService.

Fake repositories copy the exact pattern test_phone_login.py already
established (fakes implementing the real Protocols, not mocks) — this
exercises the actual service logic, not a mocked stand-in for it.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.audit_service import AuditService
from app.application.identity.request_password_reset import RequestPasswordResetService
from app.core.email_provider_interface import EmailMessage
from app.core.exceptions import CareerCompassError
from app.domain.identity.entities import AuditEvent, PasswordResetToken, Tenant, User


class FakeTenantRepository:
    def __init__(self) -> None:
        self.tenants: dict[uuid.UUID, Tenant] = {}

    async def create(self, tenant: Tenant) -> Tenant:
        self.tenants[tenant.id] = replace(tenant)
        return replace(tenant)

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        tenant = self.tenants.get(tenant_id)
        return replace(tenant) if tenant else None

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        for tenant in self.tenants.values():
            if tenant.subdomain == subdomain:
                return replace(tenant)
        return None


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
        for user in self.users.values():
            if user.tenant_id == tenant_id and user.email == email:
                return replace(user)
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


class EmailProviderError(CareerCompassError):
    code = "EMAIL_PROVIDER_ERROR"


class FakeEmailProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent: list[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> None:
        if self.should_fail:
            raise EmailProviderError("simulated provider failure")
        self.sent.append(message)


def _make_tenant(subdomain: str = "acme") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=uuid.uuid4(),
        name="Acme",
        subdomain=subdomain,
        plan_tier="standard",
        status="active",
        created_at=now,
        updated_at=now,
    )


def _make_user(*, tenant_id: uuid.UUID, email: str = "jordan@example.com") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email=email,
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="hashed",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


_Setup = tuple[
    RequestPasswordResetService,
    FakeTenantRepository,
    FakeUserRepository,
    FakePasswordResetTokenRepository,
    FakeEmailProvider,
]


def _build(*, email_provider: FakeEmailProvider | None = None) -> _Setup:
    tenants = FakeTenantRepository()
    users = FakeUserRepository()
    reset_tokens = FakePasswordResetTokenRepository()
    audit_events = FakeAuditEventRepository()
    email_provider = email_provider or FakeEmailProvider()

    service = RequestPasswordResetService(
        tenants=tenants,
        users=users,
        reset_tokens=reset_tokens,
        tenant_context=FakeTenantContextBinder(),
        email_provider=email_provider,
        audit=AuditService(audit_events),
        frontend_base_url="https://example.com",
    )
    return service, tenants, users, reset_tokens, email_provider


@pytest.mark.unit
class TestRequestPasswordReset:
    async def test_found_user_sends_one_email_with_the_reset_link(self) -> None:
        service, tenants, users, reset_tokens, email_provider = _build()
        tenant = _make_tenant()
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id)
        await users.create(user)

        await service.execute(subdomain=tenant.subdomain, email=user.email)

        assert len(email_provider.sent) == 1
        assert email_provider.sent[0].to == user.email
        assert "https://example.com/reset-password?token=" in email_provider.sent[0].html_body
        assert len(reset_tokens.tokens) == 1

    async def test_unknown_email_returns_silently_and_sends_nothing(self) -> None:
        service, tenants, _, reset_tokens, email_provider = _build()
        tenant = _make_tenant()
        await tenants.create(tenant)

        await service.execute(subdomain=tenant.subdomain, email="nobody@example.com")

        assert email_provider.sent == []
        assert reset_tokens.tokens == {}

    async def test_unknown_subdomain_returns_silently_and_sends_nothing(self) -> None:
        service, _, _, reset_tokens, email_provider = _build()

        await service.execute(subdomain="nope", email="jordan@example.com")

        assert email_provider.sent == []
        assert reset_tokens.tokens == {}

    async def test_second_request_invalidates_the_first_token(self) -> None:
        service, tenants, users, reset_tokens, _ = _build()
        tenant = _make_tenant()
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id)
        await users.create(user)

        await service.execute(subdomain=tenant.subdomain, email=user.email)
        first_token_id = next(iter(reset_tokens.tokens))

        await service.execute(subdomain=tenant.subdomain, email=user.email)

        assert reset_tokens.tokens[first_token_id].used_at is not None
        assert len(reset_tokens.tokens) == 2

    async def test_email_provider_failure_does_not_propagate(self) -> None:
        service, tenants, users, _, _ = _build(email_provider=FakeEmailProvider(should_fail=True))
        tenant = _make_tenant()
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id)
        await users.create(user)

        # Should not raise — a provider outage must not surface as an
        # error response (that would itself leak "an account was found").
        await service.execute(subdomain=tenant.subdomain, email=user.email)
