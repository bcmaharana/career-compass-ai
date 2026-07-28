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

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.adapters.db.base import async_session_factory, set_tenant_context
from app.adapters.db.repositories import SqlAlchemyRoleRepository, SqlAlchemyUserRepository
from app.core.security import hash_password
from app.domain.identity.entities import User, UserRoleAssignment

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
