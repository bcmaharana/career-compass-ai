"""Unit tests for RequestPersonalSignupService."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.request_personal_signup import RequestPersonalSignupService
from app.core.email_provider_interface import EmailMessage
from app.core.exceptions import CareerCompassError, ConflictError
from app.domain.identity.entities import PendingSignup, Tenant
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


def _make_tenant(subdomain: str) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=uuid.uuid4(),
        name="Existing",
        subdomain=subdomain,
        plan_tier="starter",
        status="active",
        created_at=now,
        updated_at=now,
    )


_Setup = tuple[RequestPersonalSignupService, FakeTenantRepository, FakePendingSignupRepository, FakeEmailProvider]


def _build(*, email_provider: FakeEmailProvider | None = None) -> _Setup:
    tenants = FakeTenantRepository()
    pending_signups = FakePendingSignupRepository()
    email_provider = email_provider or FakeEmailProvider()

    service = RequestPersonalSignupService(
        tenants=tenants,
        pending_signups=pending_signups,
        email_provider=email_provider,
        frontend_base_url="https://example.com",
    )
    return service, tenants, pending_signups, email_provider


@pytest.mark.unit
class TestRequestPersonalSignup:
    async def test_creates_a_pending_signup_and_sends_a_verification_email(self) -> None:
        service, _, pending_signups, email_provider = _build()

        await service.execute(
            email="jordan@example.com",
            password="a-real-password-1",
            first_name="Jordan",
            last_name="Rivera",
        )

        assert len(pending_signups.signups) == 1
        signup = next(iter(pending_signups.signups.values()))
        assert signup.kind == "personal"
        assert signup.email == "jordan@example.com"
        assert signup.hashed_password != "a-real-password-1"  # actually hashed
        assert signup.agreed_to_terms_at is not None
        assert signup.terms_version == CURRENT_TERMS_VERSION

        assert len(email_provider.sent) == 1
        assert email_provider.sent[0].to == "jordan@example.com"
        assert "https://example.com/verify-email?token=" in email_provider.sent[0].html_body

    async def test_existing_account_is_rejected_immediately(self) -> None:
        service, tenants, pending_signups, email_provider = _build()
        await tenants.create(_make_tenant(derive_personal_subdomain("jordan@example.com")))

        with pytest.raises(ConflictError) as exc_info:
            await service.execute(
                email="jordan@example.com",
                password="a-real-password-1",
                first_name="Jordan",
                last_name="Rivera",
            )

        assert exc_info.value.code == "EMAIL_ALREADY_REGISTERED"
        assert pending_signups.signups == {}
        assert email_provider.sent == []

    async def test_second_request_invalidates_the_first_pending_signup(self) -> None:
        service, _, pending_signups, _ = _build()

        await service.execute(
            email="jordan@example.com",
            password="a-real-password-1",
            first_name="Jordan",
            last_name="Rivera",
        )
        first_id = next(iter(pending_signups.signups))

        await service.execute(
            email="jordan@example.com",
            password="a-different-password-2",
            first_name="Jordan",
            last_name="Rivera",
        )

        assert first_id not in pending_signups.signups
        assert len(pending_signups.signups) == 1

    async def test_email_provider_failure_propagates(self) -> None:
        service, _, _, _ = _build(email_provider=FakeEmailProvider(should_fail=True))

        # Unlike password-reset, signup surfaces a real failure — the
        # user needs to know the email didn't send, not be told to
        # "check your email" for one that never arrives.
        with pytest.raises(EmailProviderError):
            await service.execute(
                email="jordan@example.com",
                password="a-real-password-1",
                first_name="Jordan",
                last_name="Rivera",
            )
