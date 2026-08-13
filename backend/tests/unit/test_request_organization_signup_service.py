"""Unit tests for RequestOrganizationSignupService."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.request_organization_signup import (
    RequestOrganizationSignupService,
)
from app.core.email_provider_interface import EmailMessage
from app.core.exceptions import ConflictError
from app.domain.identity.entities import PendingSignup, Tenant
from app.domain.identity.legal_terms import CURRENT_TERMS_VERSION


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


class FakeEmailProvider:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> None:
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


@pytest.mark.unit
class TestRequestOrganizationSignup:
    async def test_creates_a_pending_signup_and_sends_a_verification_email(self) -> None:
        tenants = FakeTenantRepository()
        pending_signups = FakePendingSignupRepository()
        email_provider = FakeEmailProvider()
        service = RequestOrganizationSignupService(
            tenants=tenants,
            pending_signups=pending_signups,
            email_provider=email_provider,
            frontend_base_url="https://example.com",
            from_email="noreply@example.com",
        )

        await service.execute(
            tenant_name="Acme Inc",
            subdomain="acme",
            organization_name="Acme HQ",
            admin_email="admin@acme.com",
            admin_password="a-real-password-1",
            admin_first_name="Ada",
            admin_last_name="Lovelace",
        )

        assert len(pending_signups.signups) == 1
        signup = next(iter(pending_signups.signups.values()))
        assert signup.kind == "enterprise"
        assert signup.subdomain == "acme"
        assert signup.tenant_name == "Acme Inc"
        assert signup.organization_name == "Acme HQ"
        assert signup.agreed_to_terms_at is not None
        assert signup.terms_version == CURRENT_TERMS_VERSION
        assert len(email_provider.sent) == 1
        assert "https://example.com/verify-email?token=" in email_provider.sent[0].html_body

    async def test_taken_subdomain_is_rejected_immediately(self) -> None:
        tenants = FakeTenantRepository()
        await tenants.create(_make_tenant("acme"))
        pending_signups = FakePendingSignupRepository()
        service = RequestOrganizationSignupService(
            tenants=tenants,
            pending_signups=pending_signups,
            email_provider=FakeEmailProvider(),
            frontend_base_url="https://example.com",
            from_email="noreply@example.com",
        )

        with pytest.raises(ConflictError) as exc_info:
            await service.execute(
                tenant_name="Acme Inc",
                subdomain="acme",
                organization_name="Acme HQ",
                admin_email="admin@acme.com",
                admin_password="a-real-password-1",
                admin_first_name="Ada",
                admin_last_name="Lovelace",
            )

        assert exc_info.value.code == "SUBDOMAIN_TAKEN"
        assert pending_signups.signups == {}
