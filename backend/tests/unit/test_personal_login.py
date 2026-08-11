"""Unit tests for AuthenticateUserService.execute with subdomain=None
(the Personal-account login path) — fakes copied from
test_phone_login.py's established pattern.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.adapters.identity_providers.internal_jwt import InternalJWTProvider
from app.application.identity.audit_service import AuditService
from app.application.identity.authenticate_user import AuthenticateUserService
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_password
from app.domain.identity.entities import AuditEvent, Role, Tenant, User
from app.domain.identity.personal_accounts import derive_personal_subdomain


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


class FakeRoleRepository:
    async def get_by_name(self, name: str, *, tenant_id: uuid.UUID | None = None) -> Role | None:
        return None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Role]:
        return []

    async def assign_to_user(self, assignment: object) -> object:
        return assignment


class FakeAuditEventRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def list_recent(self, tenant_id: uuid.UUID, *, limit: int = 50) -> list[AuditEvent]:
        return [e for e in self.events if e.tenant_id == tenant_id][:limit]


def _make_tenant(*, subdomain: str) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=uuid.uuid4(),
        name="Personal Tenant",
        subdomain=subdomain,
        plan_tier="starter",
        status="active",
        created_at=now,
        updated_at=now,
    )


def _make_user(*, tenant_id: uuid.UUID, email: str, password: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email=email,
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password=hash_password(password),
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


_Setup = tuple[AuthenticateUserService, FakeTenantRepository, FakeUserRepository]


def _build() -> _Setup:
    tenants = FakeTenantRepository()
    users = FakeUserRepository()
    roles = FakeRoleRepository()
    audit_events = FakeAuditEventRepository()
    identity_provider = InternalJWTProvider(users, roles)

    service = AuthenticateUserService(
        tenants=tenants,
        tenant_context=FakeTenantContextBinder(),
        identity_provider=identity_provider,
        audit=AuditService(audit_events),
    )
    return service, tenants, users


@pytest.mark.unit
class TestPersonalLogin:
    async def test_omitted_subdomain_resolves_the_matching_personal_tenant(self) -> None:
        service, tenants, users = _build()
        email = "jordan@example.com"
        tenant = _make_tenant(subdomain=derive_personal_subdomain(email))
        await tenants.create(tenant)
        await users.create(_make_user(tenant_id=tenant.id, email=email, password="correct-1"))

        result = await service.execute(subdomain=None, email=email, password="correct-1")

        assert result.tenant_id == tenant.id
        assert result.email == email

    async def test_an_enterprise_tenant_is_not_reachable_by_omitting_subdomain(self) -> None:
        service, tenants, users = _build()
        email = "admin@acme.example.com"
        # Enterprise tenant, real user-chosen subdomain — not derived
        # from the email at all.
        tenant = _make_tenant(subdomain="acme-corp")
        await tenants.create(tenant)
        await users.create(_make_user(tenant_id=tenant.id, email=email, password="correct-1"))

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(subdomain=None, email=email, password="correct-1")

        assert exc_info.value.code == "INVALID_CREDENTIALS"
