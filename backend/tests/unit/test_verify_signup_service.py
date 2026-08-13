"""Unit tests for VerifySignupService.

Uses the real RegisterTenantService + InternalJWTProvider against fakes
(not mocked) — same "fakes implementing the real Protocol" convention
established elsewhere this session.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.identity_providers.internal_jwt import InternalJWTProvider
from app.application.identity.audit_service import AuditService
from app.application.identity.register_tenant import RegisterTenantService
from app.application.identity.verify_signup import VerifySignupService
from app.core.email_provider_interface import EmailMessage
from app.core.exceptions import CareerCompassError, UnauthorizedError
from app.core.security import hash_password
from app.domain.identity.entities import (
    AuditEvent,
    Organization,
    PendingSignup,
    Role,
    Tenant,
    User,
    UserRoleAssignment,
)
from app.domain.identity.legal_terms import CURRENT_TERMS_VERSION
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


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.organizations: dict[uuid.UUID, Organization] = {}

    async def create(self, organization: Organization) -> Organization:
        self.organizations[organization.id] = replace(organization)
        return replace(organization)

    async def get_by_id(self, tenant_id: uuid.UUID, org_id: uuid.UUID) -> Organization | None:
        org = self.organizations.get(org_id)
        return replace(org) if org and org.tenant_id == tenant_id else None


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
    def __init__(self) -> None:
        self._admin_role = Role(id=uuid.uuid4(), tenant_id=None, name="organization_admin")

    async def get_by_name(self, name: str, *, tenant_id: uuid.UUID | None = None) -> Role | None:
        return self._admin_role if name == "organization_admin" else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Role]:
        return [self._admin_role]

    async def assign_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment:
        return assignment


class FakeTenantContextBinder:
    async def bind(self, tenant_id: uuid.UUID) -> None:
        return None


class FakeAuditEventRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def list_recent(self, tenant_id: uuid.UUID, *, limit: int = 50) -> list[AuditEvent]:
        return [e for e in self.events if e.tenant_id == tenant_id][:limit]


class FakePendingSignupRepository:
    def __init__(self) -> None:
        self.signups: dict[uuid.UUID, PendingSignup] = {}

    async def create(self, signup: PendingSignup) -> PendingSignup:
        self.signups[signup.id] = replace(signup)
        return replace(signup)

    async def get_by_token_hash(self, token_hash: str) -> PendingSignup | None:
        for signup in self.signups.values():
            if signup.token_hash == token_hash:
                return replace(signup)
        return None

    async def delete(self, signup_id: uuid.UUID) -> None:
        self.signups.pop(signup_id, None)

    async def delete_all_for_email(self, email: str) -> None:
        for signup_id in [sid for sid, s in self.signups.items() if s.email == email]:
            del self.signups[signup_id]


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


def _make_pending(
    *,
    kind: str = "personal",
    email: str = "jordan@example.com",
    raw_token: str = "a-real-token",
    expires_delta: timedelta = timedelta(minutes=60),
    tenant_name: str | None = None,
    subdomain: str | None = None,
    organization_name: str | None = None,
) -> PendingSignup:
    now = datetime.now(UTC)
    return PendingSignup(
        id=uuid.uuid4(),
        kind=kind,
        email=email,
        hashed_password=hash_password("a-real-password-1"),
        first_name="Jordan",
        last_name="Rivera",
        tenant_name=tenant_name,
        subdomain=subdomain,
        organization_name=organization_name,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=now + expires_delta,
        created_at=now,
        agreed_to_terms_at=now,
        terms_version=CURRENT_TERMS_VERSION,
    )


def _build(*, email_should_fail: bool = False) -> tuple[
    VerifySignupService,
    FakeTenantRepository,
    FakePendingSignupRepository,
    FakeUserRepository,
    FakeEmailProvider,
]:
    tenants = FakeTenantRepository()
    organizations = FakeOrganizationRepository()
    users = FakeUserRepository()
    roles = FakeRoleRepository()
    pending_signups = FakePendingSignupRepository()
    audit_events = FakeAuditEventRepository()
    email_provider = FakeEmailProvider(should_fail=email_should_fail)

    register_tenant = RegisterTenantService(
        tenants=tenants,
        organizations=organizations,
        users=users,
        roles=roles,
        tenant_context=FakeTenantContextBinder(),
        audit=AuditService(audit_events),
    )
    identity_provider = InternalJWTProvider(users, roles)
    service = VerifySignupService(
        pending_signups=pending_signups,
        register_tenant=register_tenant,
        users=users,
        identity_provider=identity_provider,
        email_provider=email_provider,
        welcome_from_email="welcome@scaledbrain.com",
    )
    return service, tenants, pending_signups, users, email_provider


@pytest.mark.unit
class TestVerifySignup:
    async def test_valid_personal_token_creates_a_real_account_and_a_working_token(self) -> None:
        service, tenants, pending_signups, users, email_provider = _build()
        pending = _make_pending(kind="personal", raw_token="a-real-token")
        await pending_signups.create(pending)

        result = await service.execute(token="a-real-token")

        assert result.access_token
        assert result.email == "jordan@example.com"
        tenant = await tenants.get_by_subdomain(derive_personal_subdomain("jordan@example.com"))
        assert tenant is not None
        assert tenant.id == result.tenant_id
        assert pending_signups.signups == {}  # consumed

        # Real consent, carried through from the moment the signup form
        # was submitted, not fabricated at verify time.
        created_user = await users.get_by_id(result.tenant_id, result.user_id)
        assert created_user is not None
        assert created_user.agreed_to_terms_at == pending.agreed_to_terms_at
        assert created_user.terms_version == CURRENT_TERMS_VERSION

        assert len(email_provider.sent) == 1
        assert email_provider.sent[0].to == "jordan@example.com"
        assert email_provider.sent[0].from_email == "welcome@scaledbrain.com"

    async def test_welcome_email_failure_does_not_block_a_successful_verification(self) -> None:
        service, _, pending_signups, _, email_provider = _build(email_should_fail=True)
        pending = _make_pending(raw_token="a-real-token")
        await pending_signups.create(pending)

        result = await service.execute(token="a-real-token")

        assert result.access_token
        assert email_provider.sent == []

    async def test_valid_enterprise_token_creates_a_real_account_with_the_chosen_subdomain(
        self,
    ) -> None:
        service, tenants, pending_signups, _, _ = _build()
        pending = _make_pending(
            kind="enterprise",
            raw_token="a-real-token",
            tenant_name="Acme Inc",
            subdomain="acme",
            organization_name="Acme HQ",
        )
        await pending_signups.create(pending)

        result = await service.execute(token="a-real-token")

        tenant = await tenants.get_by_subdomain("acme")
        assert tenant is not None
        assert tenant.id == result.tenant_id

    async def test_expired_token_is_rejected(self) -> None:
        service, _, pending_signups, _, _ = _build()
        pending = _make_pending(raw_token="expired-token", expires_delta=timedelta(minutes=-1))
        await pending_signups.create(pending)

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="expired-token")

        assert exc_info.value.code == "INVALID_SIGNUP_TOKEN"

    async def test_unknown_token_is_rejected(self) -> None:
        service, _, _, _, _ = _build()

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="never-issued")

        assert exc_info.value.code == "INVALID_SIGNUP_TOKEN"

    async def test_token_cannot_be_reused(self) -> None:
        service, _, pending_signups, _, _ = _build()
        pending = _make_pending(raw_token="one-shot-token")
        await pending_signups.create(pending)

        await service.execute(token="one-shot-token")

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(token="one-shot-token")

        assert exc_info.value.code == "INVALID_SIGNUP_TOKEN"
