"""Integration tests for the identity module.

Exercises the full stack — API routers, application services,
repositories, RLS policies — against a real Postgres test database
(career_compass_test, see .env.test and conftest.apply_migrations_and_seed).
No mocking of the database layer here; this is deliberately the
"does the whole thing actually work together" tier, complementing the
fast, DB-free unit tests in tests/unit/.

Each test uses a fresh, randomly-suffixed subdomain rather than
truncating tables between tests — simpler, and avoids interfering with
parallel test runs.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.adapters.db.base import async_session_factory, set_tenant_context
from app.adapters.db.repositories import SqlAlchemyRoleRepository, SqlAlchemyUserRepository
from app.api.dependencies import get_email_provider, get_firebase_phone_verifier
from app.core.email_provider_interface import EmailMessage
from app.core.security import hash_password
from app.domain.identity.entities import User, UserRoleAssignment
from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations_and_seed")]


def _unique_subdomain() -> str:
    return f"test-{uuid.uuid4().hex[:12]}"


async def _register_tenant(client: AsyncClient, subdomain: str) -> dict:
    response = await client.post(
        "/api/v1/identity/tenants",
        json={
            "tenant_name": f"{subdomain} Inc",
            "subdomain": subdomain,
            "organization_name": f"{subdomain} HQ",
            "admin_email": f"admin@{subdomain}.com",
            "admin_salutation": "Ms.",
            "admin_first_name": "Admin",
            "admin_last_name": "TestUser",
            "admin_password": "correct-horse-battery",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(client: AsyncClient, subdomain: str, email: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/identity/login",
        json={"subdomain": subdomain, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestTenantRegistration:
    async def test_register_tenant_creates_tenant_org_and_admin_user(
        self, client: AsyncClient
    ) -> None:
        subdomain = _unique_subdomain()

        result = await _register_tenant(client, subdomain)

        assert result["tenant_id"]
        assert result["organization_id"]
        assert result["admin_user_id"]
        assert result["admin_email"] == f"admin@{subdomain}.com"

    async def test_duplicate_subdomain_is_rejected(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        response = await client.post(
            "/api/v1/identity/tenants",
            json={
                "tenant_name": "Someone Else",
                "subdomain": subdomain,
                "organization_name": "Someone Else HQ",
                "admin_email": "other@example.com",
                "admin_salutation": None,
                "admin_first_name": "Someone",
                "admin_last_name": "Else",
                "admin_password": "another-password-1",
            },
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SUBDOMAIN_TAKEN"


class TestLogin:
    async def test_login_with_correct_credentials_returns_token(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        result = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")

        assert result["access_token"]
        assert result["token_type"] == "bearer"
        assert result["email"] == f"admin@{subdomain}.com"
        assert result["roles"] == ["organization_admin"]

    async def test_first_login_has_no_last_login_at(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        result = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")

        assert result["last_login_at"] is None

    async def test_second_login_returns_the_previous_logins_time(
        self, client: AsyncClient
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        first = await _login(
            client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery"
        )
        assert first["last_login_at"] is None

        second = await _login(
            client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery"
        )

        # Reflects *before* this second login, not "now" — a stable
        # value to display as "Last logged in @ ...", not one that
        # already moved to the moment you're reading it.
        assert second["last_login_at"] is not None

        third = await _login(
            client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery"
        )
        assert third["last_login_at"] != second["last_login_at"]

    async def test_login_reflects_updated_salutation(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        first = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        assert first["salutation"] == "Ms."

        headers = {"Authorization": f"Bearer {first['access_token']}"}
        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": "Dr.", "first_name": "Jordan", "last_name": "Rivera"},
        )

        second = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        assert second["salutation"] == "Dr."

    async def test_login_with_wrong_password_returns_401(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        response = await client.post(
            "/api/v1/identity/login",
            json={
                "subdomain": subdomain,
                "email": f"admin@{subdomain}.com",
                "password": "wrong-password",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_with_unknown_subdomain_returns_401_not_404(
        self, client: AsyncClient
    ) -> None:
        # Deliberately the same error/status as a bad password — see
        # AuthenticateUserService's comment on not revealing whether a
        # subdomain exists.
        response = await client.post(
            "/api/v1/identity/login",
            json={
                "subdomain": "definitely-does-not-exist",
                "email": "nobody@example.com",
                "password": "irrelevant",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


class FakeEmailProvider:
    """Captures sent messages instead of calling the real Resend API —
    integration tests must not fire real emails on every run. Overridden
    in via app.dependency_overrides for the duration of TestPasswordReset
    only (see the email_provider fixture below), never left in place for
    other test classes.
    """

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def email_provider() -> Generator[FakeEmailProvider, None, None]:
    fake = FakeEmailProvider()
    app.dependency_overrides[get_email_provider] = lambda: fake
    try:
        yield fake
    finally:
        del app.dependency_overrides[get_email_provider]


def _extract_reset_token(message: EmailMessage) -> str:
    match = re.search(r"[?&]token=([^&\s\"<]+)", message.html_body)
    assert match is not None, f"no token found in email body: {message.html_body}"
    return match.group(1)


def _unique_test_phone_number() -> str:
    """A fresh, libphonenumber-valid US number per call — the 555-01XX
    block (555-0100 through 555-0199) is reserved for fictional use and
    validates as a real number, unlike arbitrary 555-XXXX numbers (see
    the docstring in test_update_user_profile_service.py's phone tests
    for the same finding). personal_phone_logins enforces genuine
    cross-test global uniqueness on this number (it's the table's
    primary key) — a single hardcoded constant here previously caused
    later test runs to collide with rows a prior run had already
    committed and never cleaned up, since this test file deliberately
    doesn't truncate tables between tests/runs.
    """
    suffix = 100 + (uuid.uuid4().int % 100)
    return f"+14155550{suffix}"


class FakePhoneVerifier:
    """Stands in for FirebasePhoneVerifier — no real Firebase project is
    configured in the integration test environment, so this returns a
    fixed E.164 number instead of ever calling Firebase. Overridden in
    via app.dependency_overrides, same pattern as email_provider above.
    """

    def __init__(self, phone_number: str | None = None) -> None:
        self.phone_number = phone_number or _unique_test_phone_number()

    def verify_phone_number(self, id_token: str) -> str:
        return self.phone_number


@pytest.fixture
def phone_verifier() -> Generator[FakePhoneVerifier, None, None]:
    fake = FakePhoneVerifier()
    app.dependency_overrides[get_firebase_phone_verifier] = lambda: fake
    try:
        yield fake
    finally:
        del app.dependency_overrides[get_firebase_phone_verifier]


class TestPasswordReset:
    async def test_request_returns_generic_success_for_unknown_email(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        response = await client.post(
            "/api/v1/identity/password-reset/request",
            json={"subdomain": subdomain, "email": "nobody@example.com"},
        )

        assert response.status_code == 200
        assert email_provider.sent == []

    async def test_request_returns_generic_success_for_unknown_subdomain(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        response = await client.post(
            "/api/v1/identity/password-reset/request",
            json={"subdomain": "definitely-does-not-exist", "email": "nobody@example.com"},
        )

        assert response.status_code == 200
        assert email_provider.sent == []

    async def test_full_reset_flow_changes_the_password(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        admin_email = f"admin@{subdomain}.com"

        request_response = await client.post(
            "/api/v1/identity/password-reset/request",
            json={"subdomain": subdomain, "email": admin_email},
        )
        assert request_response.status_code == 200
        assert len(email_provider.sent) == 1
        token = _extract_reset_token(email_provider.sent[0])

        confirm_response = await client.post(
            "/api/v1/identity/password-reset/confirm",
            json={"token": token, "new_password": "brand-new-password-1"},
        )
        assert confirm_response.status_code == 200

        # The one check that would catch a repository update() gap that
        # unit tests (in-memory fakes) can't reproduce: confirm against
        # the *real* database that the old password now fails and the
        # new one works.
        old_password_attempt = await client.post(
            "/api/v1/identity/login",
            json={"subdomain": subdomain, "email": admin_email, "password": "correct-horse-battery"},
        )
        assert old_password_attempt.status_code == 401

        new_password_attempt = await client.post(
            "/api/v1/identity/login",
            json={"subdomain": subdomain, "email": admin_email, "password": "brand-new-password-1"},
        )
        assert new_password_attempt.status_code == 200

    async def test_token_cannot_be_reused(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        admin_email = f"admin@{subdomain}.com"

        await client.post(
            "/api/v1/identity/password-reset/request",
            json={"subdomain": subdomain, "email": admin_email},
        )
        token = _extract_reset_token(email_provider.sent[0])

        first = await client.post(
            "/api/v1/identity/password-reset/confirm",
            json={"token": token, "new_password": "brand-new-password-1"},
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/identity/password-reset/confirm",
            json={"token": token, "new_password": "another-password-2"},
        )
        assert second.status_code == 401
        assert second.json()["error"]["code"] == "INVALID_RESET_TOKEN"

    async def test_expired_token_is_rejected(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        registration = await _register_tenant(client, subdomain)
        admin_email = f"admin@{subdomain}.com"

        await client.post(
            "/api/v1/identity/password-reset/request",
            json={"subdomain": subdomain, "email": admin_email},
        )

        # Backdate the token's expiry directly — the API never exposes a
        # way to do this, and there's no reason to wait 30 real minutes
        # in a test.
        async with async_session_factory() as session:
            await set_tenant_context(session, uuid.UUID(registration["tenant_id"]))
            await session.execute(
                text(
                    "UPDATE password_reset_tokens SET expires_at = :expired "
                    "WHERE tenant_id = :tenant_id"
                ),
                {
                    "expired": datetime.now(UTC) - timedelta(minutes=1),
                    "tenant_id": registration["tenant_id"],
                },
            )
            await session.commit()

        token = _extract_reset_token(email_provider.sent[0])
        response = await client.post(
            "/api/v1/identity/password-reset/confirm",
            json={"token": token, "new_password": "brand-new-password-1"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def _unique_email() -> str:
    return f"personal-{uuid.uuid4().hex[:12]}@example.com"


async def _signup_personal(
    client: AsyncClient, *, email: str, password: str, email_provider: FakeEmailProvider
) -> dict:
    """Full two-phase flow: request -> extract the real emailed token ->
    verify. Returns the /signup/verify response (a real LoginResponse,
    including a working access_token) — verification auto-logs in, no
    separate /login call needed for tests that just need a session.
    """
    request_response = await client.post(
        "/api/v1/identity/signup/personal",
        json={
            "email": email,
            "password": password,
            "first_name": "Jordan",
            "last_name": "Rivera",
            "agreed_to_terms": True,
        },
    )
    assert request_response.status_code == 202, request_response.text
    assert email_provider.sent, "expected a verification email to have been sent"
    token = _extract_reset_token(email_provider.sent[-1])

    verify_response = await client.post("/api/v1/identity/signup/verify", json={"token": token})
    assert verify_response.status_code == 200, verify_response.text
    return verify_response.json()


class TestPersonalSignup:
    async def test_no_account_exists_until_verified(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()

        request_response = await client.post(
            "/api/v1/identity/signup/personal",
            json={
                "email": email,
                "password": "a-real-password-1",
                "first_name": "Jordan",
                "last_name": "Rivera",
                "agreed_to_terms": True,
            },
        )
        assert request_response.status_code == 202

        # The real proof this is verify-then-create, not create-then-flag:
        # logging in before the link is clicked must fail — there is no
        # account yet.
        login_attempt = await client.post(
            "/api/v1/identity/login", json={"email": email, "password": "a-real-password-1"}
        )
        assert login_attempt.status_code == 401

    async def test_signup_without_agreeing_to_terms_is_rejected(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()

        response = await client.post(
            "/api/v1/identity/signup/personal",
            json={
                "email": email,
                "password": "a-real-password-1",
                "first_name": "Jordan",
                "last_name": "Rivera",
                "agreed_to_terms": False,
            },
        )

        assert response.status_code == 422
        assert email_provider.sent == []
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT count(*) FROM pending_signups WHERE email = :email"),
                {"email": email},
            )
            assert result.scalar_one() == 0

    async def test_signup_then_login_with_no_subdomain(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()
        registration = await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )

        # Verification itself auto-logs in (registration IS a real
        # LoginResponse) — also confirm a separate, later login with no
        # subdomain works too, proving the deterministic-subdomain
        # derivation is stable across requests.
        response = await client.post(
            "/api/v1/identity/login",
            json={"email": email, "password": "a-real-password-1"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access_token"]
        assert body["email"] == email
        assert body["tenant_id"] == registration["tenant_id"]

        me = await client.get(
            "/api/v1/identity/me", headers={"Authorization": f"Bearer {body['access_token']}"}
        )
        assert me.status_code == 200
        assert me.json()["user_id"] == registration["user_id"]

        # Real consent recorded on the actual users row, not just
        # implied by a successful signup — checked directly against
        # Postgres, not inferred from the API response. users has RLS,
        # so tenant context must be bound first, same as any other
        # tenant-scoped query outside a request (see set_tenant_context's
        # own docstring).
        async with async_session_factory() as session:
            await set_tenant_context(session, uuid.UUID(registration["tenant_id"]))
            result = await session.execute(
                text("SELECT agreed_to_terms_at, terms_version FROM users WHERE email = :email"),
                {"email": email},
            )
            row = result.one()
            assert row.agreed_to_terms_at is not None
            assert row.terms_version

    async def test_duplicate_email_signup_is_rejected(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()
        await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )

        response = await client.post(
            "/api/v1/identity/signup/personal",
            json={
                "email": email,
                "password": "a-different-password-2",
                "first_name": "Jordan",
                "last_name": "Rivera",
                "agreed_to_terms": True,
            },
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    async def test_expired_verification_token_is_rejected(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()
        request_response = await client.post(
            "/api/v1/identity/signup/personal",
            json={
                "email": email,
                "password": "a-real-password-1",
                "first_name": "Jordan",
                "last_name": "Rivera",
                "agreed_to_terms": True,
            },
        )
        assert request_response.status_code == 202
        token = _extract_reset_token(email_provider.sent[-1])

        async with async_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE pending_signups SET expires_at = :expired WHERE email = :email"
                ),
                {"expired": datetime.now(UTC) - timedelta(minutes=1), "email": email},
            )
            await session.commit()

        verify_response = await client.post(
            "/api/v1/identity/signup/verify", json={"token": token}
        )
        assert verify_response.status_code == 401
        assert verify_response.json()["error"]["code"] == "INVALID_SIGNUP_TOKEN"

    async def test_enterprise_admin_cannot_login_by_omitting_subdomain(
        self, client: AsyncClient
    ) -> None:
        subdomain = _unique_subdomain()
        registration = await _register_tenant(client, subdomain)

        response = await client.post(
            "/api/v1/identity/login",
            json={
                "email": f"admin@{subdomain}.com",
                "password": "correct-horse-battery",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
        # Confirm it's a real rejection, not a coincidental cross-tenant
        # match — the enterprise account still logs in fine with its
        # real subdomain.
        assert registration["tenant_id"]


class TestOrganizationSignup:
    async def test_no_account_exists_until_verified(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()

        request_response = await client.post(
            "/api/v1/identity/signup/organization",
            json={
                "tenant_name": f"{subdomain} Inc",
                "subdomain": subdomain,
                "organization_name": f"{subdomain} HQ",
                "admin_email": f"admin@{subdomain}.com",
                "admin_first_name": "Ada",
                "admin_last_name": "Lovelace",
                "admin_password": "a-real-password-1",
                "agreed_to_terms": True,
            },
        )
        assert request_response.status_code == 202

        login_attempt = await client.post(
            "/api/v1/identity/login",
            json={
                "subdomain": subdomain,
                "email": f"admin@{subdomain}.com",
                "password": "a-real-password-1",
            },
        )
        assert login_attempt.status_code == 401

    async def test_signup_then_login_with_chosen_subdomain(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        admin_email = f"admin@{subdomain}.com"

        request_response = await client.post(
            "/api/v1/identity/signup/organization",
            json={
                "tenant_name": f"{subdomain} Inc",
                "subdomain": subdomain,
                "organization_name": f"{subdomain} HQ",
                "admin_email": admin_email,
                "admin_first_name": "Ada",
                "admin_last_name": "Lovelace",
                "admin_password": "a-real-password-1",
                "agreed_to_terms": True,
            },
        )
        assert request_response.status_code == 202
        token = _extract_reset_token(email_provider.sent[-1])

        verify_response = await client.post(
            "/api/v1/identity/signup/verify", json={"token": token}
        )
        assert verify_response.status_code == 200, verify_response.text
        assert verify_response.json()["email"] == admin_email

        response = await client.post(
            "/api/v1/identity/login",
            json={"subdomain": subdomain, "email": admin_email, "password": "a-real-password-1"},
        )
        assert response.status_code == 200

    async def test_taken_subdomain_signup_is_rejected(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)

        response = await client.post(
            "/api/v1/identity/signup/organization",
            json={
                "tenant_name": "Someone Else",
                "subdomain": subdomain,
                "organization_name": "Someone Else HQ",
                "admin_email": "other@example.com",
                "admin_first_name": "Someone",
                "admin_last_name": "Else",
                "admin_password": "a-real-password-1",
                "agreed_to_terms": True,
            },
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SUBDOMAIN_TAKEN"


class TestPersonalPhoneLogin:
    """Phone login for Personal accounts — resolves the tenant via
    personal_phone_logins instead of a caller-supplied subdomain. See
    AuthenticateUserService.execute_phone.
    """

    async def test_registered_phone_number_logs_in_with_no_subdomain(
        self,
        client: AsyncClient,
        email_provider: FakeEmailProvider,
        phone_verifier: FakePhoneVerifier,
    ) -> None:
        email = _unique_email()
        registration = await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )
        headers = {"Authorization": f"Bearer {registration['access_token']}"}

        profile_update = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "phone_number": phone_verifier.phone_number,
                "country": "US",
            },
        )
        assert profile_update.status_code == 200, profile_update.text

        response = await client.post(
            "/api/v1/identity/login/phone",
            json={"subdomain": None, "firebase_id_token": "good-token"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] == registration["user_id"]
        assert body["tenant_id"] == registration["tenant_id"]

    async def test_unregistered_phone_number_is_rejected(
        self, client: AsyncClient, phone_verifier: FakePhoneVerifier
    ) -> None:
        response = await client.post(
            "/api/v1/identity/login/phone",
            json={"subdomain": None, "firebase_id_token": "good-token"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_enterprise_phone_login_still_requires_subdomain(
        self, client: AsyncClient, phone_verifier: FakePhoneVerifier
    ) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Admin",
                "last_name": "TestUser",
                "phone_number": phone_verifier.phone_number,
                "country": "US",
            },
        )

        # Enterprise numbers are never registered in personal_phone_logins
        # (see UpdateUserProfileService) — omitting the subdomain must
        # still fail even though the number is real and saved.
        no_subdomain = await client.post(
            "/api/v1/identity/login/phone",
            json={"subdomain": None, "firebase_id_token": "good-token"},
        )
        assert no_subdomain.status_code == 401

        with_subdomain = await client.post(
            "/api/v1/identity/login/phone",
            json={"subdomain": subdomain, "firebase_id_token": "good-token"},
        )
        assert with_subdomain.status_code == 200, with_subdomain.text


class TestDeleteAccount:
    async def test_delete_removes_personal_phone_login_lookup(
        self,
        client: AsyncClient,
        email_provider: FakeEmailProvider,
        phone_verifier: FakePhoneVerifier,
    ) -> None:
        """A registered phone-login number must not survive account
        deletion — orphaning it would either leak a stale tenant
        mapping or (given phone_number_e164 is the table's primary key)
        permanently block a future account from ever claiming that
        number. Also proves PersonalPhoneLoginModel's presence in
        SqlAlchemyAccountDeletionRepository's step-3 delete loop doesn't
        raise an FK violation against the users table it references.
        """
        email = _unique_email()
        registration = await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )
        headers = {"Authorization": f"Bearer {registration['access_token']}"}

        profile_update = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "phone_number": phone_verifier.phone_number,
                "country": "US",
            },
        )
        assert profile_update.status_code == 200, profile_update.text

        delete_response = await client.delete("/api/v1/identity/me", headers=headers)
        assert delete_response.status_code == 204

        phone_login_attempt = await client.post(
            "/api/v1/identity/login/phone",
            json={"subdomain": None, "firebase_id_token": "good-token"},
        )
        assert phone_login_attempt.status_code == 401

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT count(*) FROM personal_phone_logins WHERE phone_number_e164 = :number"
                ),
                {"number": phone_verifier.phone_number},
            )
            assert result.scalar_one() == 0

    async def test_delete_removes_platform_admin_grant(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        """A platform_admins row referencing this user (NOT NULL FK on
        both tenant_id and user_id, no ON DELETE CASCADE) must not block
        deletion — the exact bug caught live building the platform-admin
        feature: deleting an account that held a platform_admins grant
        raised a raw ForeignKeyViolation 500 before PlatformAdminModel
        was added to SqlAlchemyAccountDeletionRepository's step-3 delete
        loop. Inserted directly (no self-grant API exists), same as
        this class's phone-login sibling test.
        """
        email = _unique_email()
        registration = await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )
        headers = {"Authorization": f"Bearer {registration['access_token']}"}
        tenant_id = uuid.UUID(registration["tenant_id"])
        user_id = uuid.UUID(registration["user_id"])

        async with async_session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO platform_admins
                        (id, tenant_id, user_id, email, full_name, permission_codes, granted_by_user_id)
                    VALUES
                        (:id, :tenant_id, :user_id, :email, :full_name, :permission_codes, :user_id)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "email": email,
                    "full_name": "Jordan Rivera",
                    "permission_codes": '["platform.settings.view"]',
                },
            )
            await session.commit()

        delete_response = await client.delete("/api/v1/identity/me", headers=headers)
        assert delete_response.status_code == 204, delete_response.text

        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT count(*) FROM platform_admins WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            assert result.scalar_one() == 0

    async def test_delete_removes_the_tenant_and_login_then_fails(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email = _unique_email()
        registration = await _signup_personal(
            client, email=email, password="a-real-password-1", email_provider=email_provider
        )
        headers = {"Authorization": f"Bearer {registration['access_token']}"}
        tenant_id = registration["tenant_id"]

        # Add some real data so this actually exercises the multi-table
        # delete, not just an empty tenant.
        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": None, "first_name": "Jordan", "last_name": "Rivera"},
        )
        await client.get("/api/v1/career-profile", headers=headers)  # auto-creates a profile

        delete_response = await client.delete("/api/v1/identity/me", headers=headers)
        assert delete_response.status_code == 204

        login_attempt = await client.post(
            "/api/v1/identity/login", json={"email": email, "password": "a-real-password-1"}
        )
        assert login_attempt.status_code == 401

        # Confirm it's genuinely gone from Postgres, not just
        # unreachable via the login path.
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT count(*) FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
            assert result.scalar_one() == 0

    async def test_delete_does_not_affect_other_tenants(
        self, client: AsyncClient, email_provider: FakeEmailProvider
    ) -> None:
        email_a = _unique_email()
        email_b = _unique_email()
        registration_a = await _signup_personal(
            client, email=email_a, password="a-real-password-1", email_provider=email_provider
        )
        registration_b = await _signup_personal(
            client, email=email_b, password="a-real-password-1", email_provider=email_provider
        )

        await client.delete(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {registration_a['access_token']}"},
        )

        # Tenant B's account is completely unaffected.
        login_b = await client.post(
            "/api/v1/identity/login", json={"email": email_b, "password": "a-real-password-1"}
        )
        assert login_b.status_code == 200
        assert login_b.json()["tenant_id"] == registration_b["tenant_id"]


class TestCurrentUser:
    async def test_me_requires_a_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/identity/me")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "MISSING_TOKEN"

    async def test_me_rejects_an_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/identity/me", headers={"Authorization": "Bearer not-a-real-token"}
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_TOKEN"

    async def test_me_returns_the_authenticated_user(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        registration = await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")

        response = await client.get(
            "/api/v1/identity/me", headers={"Authorization": f"Bearer {login['access_token']}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == registration["admin_user_id"]
        assert body["tenant_id"] == registration["tenant_id"]
        assert body["roles"] == ["organization_admin"]


class TestUpdateCurrentUser:
    async def test_updates_name_and_salutation(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": "Dr.", "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["first_name"] == "Jordan"
        assert body["last_name"] == "Rivera"
        assert body["salutation"] == "Dr."
        assert body["full_name"] == "Dr. Jordan Rivera"

        # Persisted, not just echoed back.
        follow_up = await client.get("/api/v1/identity/me", headers=headers)
        assert follow_up.json()["first_name"] == "Jordan"
        assert follow_up.json()["last_name"] == "Rivera"

    async def test_blank_salutation_clears_it(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": "", "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["salutation"] is None
        assert body["full_name"] == "Jordan Rivera"

    async def test_rejects_blank_first_name(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": None, "first_name": "", "last_name": "Rivera"},
        )

        # Pydantic's min_length=1 on UpdateCurrentUserRequest.first_name
        # rejects this before it ever reaches the service.
        assert response.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.patch(
            "/api/v1/identity/me",
            json={"salutation": None, "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 401

    async def test_updates_and_persists_phone_number(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "phone_number": "+1 (555) 123-4567",
            },
        )

        assert response.status_code == 200
        assert response.json()["phone_number"] == "+1 (555) 123-4567"

        follow_up = await client.get("/api/v1/identity/me", headers=headers)
        assert follow_up.json()["phone_number"] == "+1 (555) 123-4567"

    async def test_omitting_phone_number_is_allowed(self, client: AsyncClient) -> None:
        # Optional field — existing PATCH callers that don't know about
        # it yet must not be forced to start sending it.
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": None, "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 200
        assert response.json()["phone_number"] is None

    async def test_blank_phone_number_clears_it(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "phone_number": "555-123-4567",
            },
        )

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "phone_number": "   ",
            },
        )

        assert response.json()["phone_number"] is None

    async def test_updates_and_persists_country_language(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "country": "us",
                "language": "en-US",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["country"] == "US"
        assert body["language"] == "en-US"

        follow_up = await client.get("/api/v1/identity/me", headers=headers)
        follow_up_body = follow_up.json()
        assert follow_up_body["country"] == "US"
        assert follow_up_body["language"] == "en-US"

    async def test_omitting_country_language_is_allowed(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": None, "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["country"] is None
        assert body["language"] is None

    async def test_blank_country_language_clears_them(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "country": "GB",
                "language": "en",
            },
        )

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "country": "",
                "language": "   ",
            },
        )

        body = response.json()
        assert body["country"] is None
        assert body["language"] is None

    async def test_updates_and_persists_structured_address(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "address_line1": "123 Main St",
                "address_line2": "Apt 4B",
                "city": "Springfield",
                "state": "IL",
                "postal_code": "62701",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["address_line1"] == "123 Main St"
        assert body["address_line2"] == "Apt 4B"
        assert body["city"] == "Springfield"
        assert body["state"] == "IL"
        assert body["postal_code"] == "62701"

        follow_up = await client.get("/api/v1/identity/me", headers=headers)
        follow_up_body = follow_up.json()
        assert follow_up_body["address_line1"] == "123 Main St"
        assert follow_up_body["address_line2"] == "Apt 4B"
        assert follow_up_body["city"] == "Springfield"
        assert follow_up_body["state"] == "IL"
        assert follow_up_body["postal_code"] == "62701"

    async def test_omitting_address_fields_is_allowed(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={"salutation": None, "first_name": "Jordan", "last_name": "Rivera"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["address_line1"] is None
        assert body["address_line2"] is None
        assert body["city"] is None
        assert body["state"] is None
        assert body["postal_code"] is None

    async def test_blank_address_fields_clear_them(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "address_line1": "1 Downing St",
                "city": "London",
                "postal_code": "SW1A 2AA",
            },
        )

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "address_line1": "   ",
                "city": "   ",
                "postal_code": "   ",
            },
        )

        body = response.json()
        assert body["address_line1"] is None
        assert body["city"] is None
        assert body["postal_code"] is None

    async def test_rejects_invalid_country_code(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        response = await client.patch(
            "/api/v1/identity/me",
            headers=headers,
            json={
                "salutation": None,
                "first_name": "Jordan",
                "last_name": "Rivera",
                "country": "USA",
            },
        )

        assert response.status_code == 422


async def _create_employee_user(tenant_id: str, subdomain: str) -> str:
    """Creates a user with only the 'employee' role, bypassing the API
    (no user-management endpoint exists yet — that's Phase 2+ scope).
    Returns the plaintext password so the test can log in as this user.
    """
    password = "employee-password-1"
    async with async_session_factory() as session:
        await set_tenant_context(session, uuid.UUID(tenant_id))

        users = SqlAlchemyUserRepository(session)
        roles = SqlAlchemyRoleRepository(session)

        user = await users.create(
            User(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                org_id=None,
                email=f"employee@{subdomain}.com",
                salutation=None,
                first_name="Employee",
                last_name="TestUser",
                hashed_password=hash_password(password),
                status="active",
                mfa_enabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        employee_role = await roles.get_by_name("employee", tenant_id=None)
        assert employee_role is not None, "employee role must be seeded (see conftest fixture)"

        await roles.assign_to_user(
            UserRoleAssignment(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                user_id=user.id,
                role_id=employee_role.id,
                org_id=None,
            )
        )
        await session.commit()

    return password


class TestRoleBasedAccessControl:
    async def test_org_admin_can_read_audit_events(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        await _register_tenant(client, subdomain)
        login = await _login(client, subdomain, f"admin@{subdomain}.com", "correct-horse-battery")

        response = await client.get(
            "/api/v1/identity/audit-events",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )

        assert response.status_code == 200
        actions = {event["action"] for event in response.json()}
        assert "tenant.created" in actions
        assert "user.created" in actions
        assert "auth.login_success" in actions

    async def test_employee_role_is_denied_audit_events(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        registration = await _register_tenant(client, subdomain)
        password = await _create_employee_user(registration["tenant_id"], subdomain)

        login = await _login(client, subdomain, f"employee@{subdomain}.com", password)

        response = await client.get(
            "/api/v1/identity/audit-events",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    async def test_employee_role_can_still_read_own_profile(self, client: AsyncClient) -> None:
        subdomain = _unique_subdomain()
        registration = await _register_tenant(client, subdomain)
        password = await _create_employee_user(registration["tenant_id"], subdomain)

        login = await _login(client, subdomain, f"employee@{subdomain}.com", password)

        response = await client.get(
            "/api/v1/identity/me", headers={"Authorization": f"Bearer {login['access_token']}"}
        )

        assert response.status_code == 200
        assert response.json()["roles"] == ["employee"]


class TestCrossTenantIsolation:
    async def test_audit_events_never_leak_across_tenants(self, client: AsyncClient) -> None:
        subdomain_a = _unique_subdomain()
        subdomain_b = _unique_subdomain()
        await _register_tenant(client, subdomain_a)
        await _register_tenant(client, subdomain_b)

        login_a = await _login(
            client, subdomain_a, f"admin@{subdomain_a}.com", "correct-horse-battery"
        )
        login_b = await _login(
            client, subdomain_b, f"admin@{subdomain_b}.com", "correct-horse-battery"
        )

        events_a = await client.get(
            "/api/v1/identity/audit-events",
            headers={"Authorization": f"Bearer {login_a['access_token']}"},
        )
        events_b = await client.get(
            "/api/v1/identity/audit-events",
            headers={"Authorization": f"Bearer {login_b['access_token']}"},
        )

        emails_seen_by_a = {e["metadata"].get("email") for e in events_a.json()}
        emails_seen_by_b = {e["metadata"].get("email") for e in events_b.json()}

        assert f"admin@{subdomain_a}.com" in emails_seen_by_a
        assert f"admin@{subdomain_b}.com" not in emails_seen_by_a
        assert f"admin@{subdomain_b}.com" in emails_seen_by_b
        assert f"admin@{subdomain_a}.com" not in emails_seen_by_b

    async def test_current_user_tenant_id_matches_own_tenant_only(
        self, client: AsyncClient
    ) -> None:
        subdomain_a = _unique_subdomain()
        subdomain_b = _unique_subdomain()
        registration_a = await _register_tenant(client, subdomain_a)
        registration_b = await _register_tenant(client, subdomain_b)

        login_a = await _login(
            client, subdomain_a, f"admin@{subdomain_a}.com", "correct-horse-battery"
        )

        response = await client.get(
            "/api/v1/identity/me", headers={"Authorization": f"Bearer {login_a['access_token']}"}
        )

        assert response.json()["tenant_id"] == registration_a["tenant_id"]
        assert response.json()["tenant_id"] != registration_b["tenant_id"]
