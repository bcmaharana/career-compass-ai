"""Integration tests for the (simplified, per ADR-005) Skill Intelligence
module — real API calls through httpx against the real test database, no
mocking. Follows the pattern established in test_career_profile_flow.py.

Only GET /skills/gap-analysis lives under this module now; My Skills and
Target Role Skill Requirements are exercised via the career-profile
endpoints in test_career_profile_flow.py (TestCoreCompetencies,
TestTargetRoleRequiredSkills) since that's where the underlying data
(core_competencies, required_skills) actually lives.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations_and_seed")]


def _unique_subdomain() -> str:
    return f"skilltest-{uuid.uuid4().hex[:12]}"


async def _register_and_login(client: AsyncClient) -> tuple[str, dict]:
    subdomain = _unique_subdomain()
    registration = await client.post(
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
    assert registration.status_code == 201, registration.text
    reg_body = registration.json()

    login = await client.post(
        "/api/v1/identity/login",
        json={
            "subdomain": subdomain,
            "email": f"admin@{subdomain}.com",
            "password": "correct-horse-battery",
        },
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], reg_body


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestGapAnalysis:
    async def test_no_target_roles_means_no_gaps(self, client: AsyncClient) -> None:
        token, _ = await _register_and_login(client)

        response = await client.get("/api/v1/skills/gap-analysis", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["target_role_gaps"] == []

    async def test_missing_required_skills_produce_a_gap(self, client: AsyncClient) -> None:
        token, _ = await _register_and_login(client)

        await client.patch(
            "/api/v1/career-profile",
            headers=_auth(token),
            json={"headline": None, "summary": None, "core_competencies": ["Python"]},
        )
        role = (
            await client.post(
                "/api/v1/career-profile/target-roles",
                headers=_auth(token),
                json={"role_name": "Staff Engineer", "tag": "SE"},
            )
        ).json()
        for name in ("Python", "SQL"):
            await client.post(
                f"/api/v1/career-profile/target-roles/{role['id']}/required-skills",
                headers=_auth(token),
                json={"name": name},
            )

        response = await client.get("/api/v1/skills/gap-analysis", headers=_auth(token))

        assert response.status_code == 200
        gaps = response.json()["target_role_gaps"]
        assert len(gaps) == 1
        assert gaps[0]["target_role_id"] == role["id"]
        assert gaps[0]["role_name"] == "Staff Engineer"
        assert gaps[0]["tag"] == "SE"
        assert gaps[0]["missing_skills"] == ["SQL"]

    async def test_matching_is_case_insensitive(self, client: AsyncClient) -> None:
        token, _ = await _register_and_login(client)

        await client.patch(
            "/api/v1/career-profile",
            headers=_auth(token),
            json={"headline": None, "summary": None, "core_competencies": ["python"]},
        )
        role = (
            await client.post(
                "/api/v1/career-profile/target-roles",
                headers=_auth(token),
                json={"role_name": "Staff Engineer", "tag": "SE"},
            )
        ).json()
        await client.post(
            f"/api/v1/career-profile/target-roles/{role['id']}/required-skills",
            headers=_auth(token),
            json={"name": "PYTHON"},
        )

        response = await client.get("/api/v1/skills/gap-analysis", headers=_auth(token))

        assert response.json()["target_role_gaps"] == []

    async def test_removing_a_competency_reintroduces_the_gap(self, client: AsyncClient) -> None:
        token, _ = await _register_and_login(client)

        await client.patch(
            "/api/v1/career-profile",
            headers=_auth(token),
            json={"headline": None, "summary": None, "core_competencies": ["Python"]},
        )
        role = (
            await client.post(
                "/api/v1/career-profile/target-roles",
                headers=_auth(token),
                json={"role_name": "Staff Engineer", "tag": "SE"},
            )
        ).json()
        await client.post(
            f"/api/v1/career-profile/target-roles/{role['id']}/required-skills",
            headers=_auth(token),
            json={"name": "Python"},
        )
        assert (
            await client.get("/api/v1/skills/gap-analysis", headers=_auth(token))
        ).json()["target_role_gaps"] == []

        await client.patch(
            "/api/v1/career-profile",
            headers=_auth(token),
            json={"headline": None, "summary": None, "core_competencies": []},
        )

        response = await client.get("/api/v1/skills/gap-analysis", headers=_auth(token))
        gaps = response.json()["target_role_gaps"]
        assert len(gaps) == 1
        assert gaps[0]["missing_skills"] == ["Python"]

    async def test_users_in_the_same_tenant_have_independent_gap_analyses(
        self, client: AsyncClient
    ) -> None:
        """Mirrors TestCrossUserIsolation in test_career_profile_flow.py
        — RLS covers cross-tenant isolation (test_identity_flow.py); this
        covers the application-level ownership boundary gap analysis
        depends on transitively via CareerProfileService/TargetRoleService.
        """
        token_a, _ = await _register_and_login(client)
        token_b, _ = await _register_and_login(client)

        await client.patch(
            "/api/v1/career-profile",
            headers=_auth(token_a),
            json={"headline": None, "summary": None, "core_competencies": []},
        )
        role_a = (
            await client.post(
                "/api/v1/career-profile/target-roles",
                headers=_auth(token_a),
                json={"role_name": "A's role", "tag": "AR"},
            )
        ).json()
        await client.post(
            f"/api/v1/career-profile/target-roles/{role_a['id']}/required-skills",
            headers=_auth(token_a),
            json={"name": "Python"},
        )

        response_b = await client.get("/api/v1/skills/gap-analysis", headers=_auth(token_b))

        assert response_b.json()["target_role_gaps"] == []

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/skills/gap-analysis")

        assert response.status_code == 401
