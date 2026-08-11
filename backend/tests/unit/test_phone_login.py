"""Unit tests for phone login (AuthenticateUserService.execute_phone).

Uses a real InternalJWTProvider + AuditService against fakes, plus a
fake phone verifier (never touches the real Firebase SDK) — the same
"fakes implementing the real Protocol" convention as
test_update_user_profile_service.py, so this exercises the actual
authenticate_with_phone lookup/claims logic, not a mocked stand-in for it.
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
from app.domain.identity.entities import AuditEvent, Role, Tenant, User


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
        for user in self.users.values():
            if user.tenant_id == tenant_id and user.phone_number_e164 == phone_e164:
                return replace(user)
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


class FakePersonalPhoneLoginRepository:
    def __init__(self) -> None:
        # phone_e164 -> tenant_id
        self.rows: dict[str, uuid.UUID] = {}

    async def upsert(self, *, phone_e164: str, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.rows[phone_e164] = tenant_id

    async def get_tenant_id(self, phone_e164: str) -> uuid.UUID | None:
        return self.rows.get(phone_e164)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        return None


class FakePhoneVerifier:
    """Stands in for FirebasePhoneVerifier — returns a fixed E.164 number
    instead of ever calling the real Firebase SDK/network."""

    def __init__(self, phone_number: str = "+14155552671") -> None:
        self.phone_number = phone_number
        self.received_tokens: list[str] = []

    def verify_phone_number(self, id_token: str) -> str:
        self.received_tokens.append(id_token)
        if id_token == "bad-token":
            raise UnauthorizedError(
                "Invalid or expired phone verification.", code="INVALID_PHONE_TOKEN"
            )
        return self.phone_number


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


def _make_user(*, tenant_id: uuid.UUID, phone_number_e164: str | None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="hashed",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
        phone_number_e164=phone_number_e164,
    )


_Setup = tuple[AuthenticateUserService, FakeTenantRepository, FakeUserRepository, FakePhoneVerifier]


@pytest.fixture
def setup() -> _Setup:
    tenants = FakeTenantRepository()
    users = FakeUserRepository()
    roles = FakeRoleRepository()
    audit_events = FakeAuditEventRepository()
    identity_provider = InternalJWTProvider(users, roles)
    phone_verifier = FakePhoneVerifier()

    service = AuthenticateUserService(
        tenants=tenants,
        tenant_context=FakeTenantContextBinder(),
        identity_provider=identity_provider,
        audit=AuditService(audit_events),
        phone_verifier=phone_verifier,
    )
    return service, tenants, users, phone_verifier


@pytest.mark.unit
class TestPhoneLogin:
    async def test_successful_phone_login_issues_token_for_matching_user(self, setup) -> None:
        service, tenants, users, verifier = setup
        tenant = _make_tenant()
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id, phone_number_e164=verifier.phone_number)
        await users.create(user)

        result = await service.execute_phone(
            subdomain=tenant.subdomain, firebase_id_token="good-token"
        )

        assert result.user_id == user.id
        assert result.tenant_id == tenant.id
        assert result.email == user.email
        assert result.access_token
        assert verifier.received_tokens == ["good-token"]

    async def test_unknown_subdomain_is_rejected(self, setup) -> None:
        service, _, _, _ = setup

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain="nope", firebase_id_token="good-token")

        assert exc_info.value.code == "INVALID_CREDENTIALS"

    async def test_verified_phone_with_no_matching_user_is_rejected(self, setup) -> None:
        service, tenants, _, _ = setup
        tenant = _make_tenant()
        await tenants.create(tenant)

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain=tenant.subdomain, firebase_id_token="good-token")

        assert exc_info.value.code == "INVALID_CREDENTIALS"

    async def test_invalid_firebase_token_is_rejected(self, setup) -> None:
        service, tenants, _, _ = setup
        tenant = _make_tenant()
        await tenants.create(tenant)

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain=tenant.subdomain, firebase_id_token="bad-token")

        assert exc_info.value.code == "INVALID_PHONE_TOKEN"

    async def test_a_users_phone_number_only_matches_within_its_own_tenant(self, setup) -> None:
        service, tenants, users, verifier = setup
        tenant_a = _make_tenant("acme")
        tenant_b = _make_tenant("globex")
        await tenants.create(tenant_a)
        await tenants.create(tenant_b)
        # User's phone is registered under tenant_a only.
        user = _make_user(tenant_id=tenant_a.id, phone_number_e164=verifier.phone_number)
        await users.create(user)

        with pytest.raises(UnauthorizedError):
            await service.execute_phone(
                subdomain=tenant_b.subdomain, firebase_id_token="good-token"
            )

    async def test_phone_login_not_configured_without_a_verifier(self) -> None:
        tenants = FakeTenantRepository()
        users = FakeUserRepository()
        tenant = _make_tenant()
        await tenants.create(tenant)
        service = AuthenticateUserService(
            tenants=tenants,
            tenant_context=FakeTenantContextBinder(),
            identity_provider=InternalJWTProvider(users, FakeRoleRepository()),
            audit=AuditService(FakeAuditEventRepository()),
            phone_verifier=None,
        )

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain=tenant.subdomain, firebase_id_token="good-token")

        assert exc_info.value.code == "PHONE_LOGIN_NOT_CONFIGURED"


@pytest.mark.unit
class TestPersonalPhoneLogin:
    """Blank/omitted subdomain means Personal account — resolved via
    personal_phone_logins instead of get_by_subdomain. See
    AuthenticateUserService.execute_phone's docstring."""

    def _service(
        self,
    ) -> tuple[
        AuthenticateUserService,
        FakeTenantRepository,
        FakeUserRepository,
        FakePersonalPhoneLoginRepository,
        FakePhoneVerifier,
    ]:
        tenants = FakeTenantRepository()
        users = FakeUserRepository()
        roles = FakeRoleRepository()
        audit_events = FakeAuditEventRepository()
        identity_provider = InternalJWTProvider(users, roles)
        phone_verifier = FakePhoneVerifier()
        personal_phone_logins = FakePersonalPhoneLoginRepository()

        service = AuthenticateUserService(
            tenants=tenants,
            tenant_context=FakeTenantContextBinder(),
            identity_provider=identity_provider,
            audit=AuditService(audit_events),
            phone_verifier=phone_verifier,
            personal_phone_logins=personal_phone_logins,
        )
        return service, tenants, users, personal_phone_logins, phone_verifier

    async def test_registered_personal_number_succeeds_with_no_subdomain(self) -> None:
        service, tenants, users, personal_phone_logins, verifier = self._service()
        tenant = _make_tenant(subdomain="p-abc123")
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id, phone_number_e164=verifier.phone_number)
        await users.create(user)
        personal_phone_logins.rows[verifier.phone_number] = tenant.id

        result = await service.execute_phone(subdomain=None, firebase_id_token="good-token")

        assert result.user_id == user.id
        assert result.tenant_id == tenant.id

    async def test_unregistered_personal_number_is_rejected(self) -> None:
        service, _, _, _, _ = self._service()

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain=None, firebase_id_token="good-token")

        assert exc_info.value.code == "INVALID_CREDENTIALS"

    async def test_blank_string_subdomain_is_treated_the_same_as_none(self) -> None:
        # "" is falsy, same as None — the frontend never sends an empty
        # string on purpose, but a defensive check either way shouldn't
        # accidentally fall through to get_by_subdomain("").
        service, tenants, users, personal_phone_logins, verifier = self._service()
        tenant = _make_tenant(subdomain="p-abc123")
        await tenants.create(tenant)
        user = _make_user(tenant_id=tenant.id, phone_number_e164=verifier.phone_number)
        await users.create(user)
        personal_phone_logins.rows[verifier.phone_number] = tenant.id

        result = await service.execute_phone(subdomain="", firebase_id_token="good-token")

        assert result.tenant_id == tenant.id

    async def test_no_personal_phone_login_repository_configured_is_rejected(self) -> None:
        tenants = FakeTenantRepository()
        users = FakeUserRepository()
        tenant = _make_tenant(subdomain="p-abc123")
        await tenants.create(tenant)
        verifier = FakePhoneVerifier()
        user = _make_user(tenant_id=tenant.id, phone_number_e164=verifier.phone_number)
        await users.create(user)
        service = AuthenticateUserService(
            tenants=tenants,
            tenant_context=FakeTenantContextBinder(),
            identity_provider=InternalJWTProvider(users, FakeRoleRepository()),
            audit=AuditService(FakeAuditEventRepository()),
            phone_verifier=verifier,
            personal_phone_logins=None,
        )

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute_phone(subdomain=None, firebase_id_token="good-token")

        assert exc_info.value.code == "INVALID_CREDENTIALS"
