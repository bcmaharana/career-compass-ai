"""Unit tests for AuthenticateUserService.execute — now permanently
disabled per ADR-002's cutover decision (see that file's own docstring):
all real authentication happens through the platform's federated
handoff, not a local email/password check against this app's own
database. This file used to test the subdomain-resolution logic
execute() ran before reaching a password check; that logic was removed
entirely, not just gated, so these tests were rewritten to verify the
new (and now only) behavior — an immediate, unconditional rejection,
regardless of what's passed in.
"""

from __future__ import annotations

import pytest

from app.application.identity.audit_service import AuditService
from app.application.identity.authenticate_user import AuthenticateUserService
from app.core.exceptions import UnauthorizedError


class FakeTenantRepository:
    async def get_by_id(self, tenant_id: object) -> None:
        return None

    async def get_by_subdomain(self, subdomain: str) -> None:
        return None


class FakeTenantContextBinder:
    async def bind(self, tenant_id: object) -> None:
        return None


class FakeAuditEventRepository:
    async def record(self, event: object) -> object:
        return event

    async def list_recent(self, tenant_id: object, *, limit: int = 50) -> list[object]:
        return []


def _build() -> AuthenticateUserService:
    return AuthenticateUserService(
        tenants=FakeTenantRepository(),  # type: ignore[arg-type]
        tenant_context=FakeTenantContextBinder(),
        identity_provider=None,  # type: ignore[arg-type]
        audit=AuditService(FakeAuditEventRepository()),  # type: ignore[arg-type]
    )


@pytest.mark.unit
class TestLocalPasswordLoginDisabled:
    async def test_execute_always_raises_regardless_of_credentials(self) -> None:
        service = _build()

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(subdomain=None, email="jordan@example.com", password="anything")

        assert exc_info.value.code == "LOCAL_LOGIN_DISABLED"

    async def test_execute_raises_even_for_an_enterprise_style_subdomain(self) -> None:
        service = _build()

        with pytest.raises(UnauthorizedError) as exc_info:
            await service.execute(
                subdomain="acme-corp", email="admin@acme.example.com", password="anything"
            )

        assert exc_info.value.code == "LOCAL_LOGIN_DISABLED"
