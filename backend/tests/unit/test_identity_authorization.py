"""Unit tests for app.domain.identity.authorization.

Pure domain logic — no database, no HTTP, no fixtures beyond plain
Python objects. This is the layer where authorization *rules* should be
tested; whether the API correctly wires a user's roles into these rules
is covered separately in tests/integration/test_identity_flow.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.identity.authorization import has_any_permission, has_permission
from app.domain.identity.entities import Role


def _role(name: str, *permission_codes: str) -> Role:
    return Role(
        id=uuid.uuid4(), tenant_id=None, name=name, permission_codes=frozenset(permission_codes)
    )


@pytest.mark.unit
class TestHasPermission:
    def test_grants_when_a_role_has_the_permission(self) -> None:
        roles = [_role("organization_admin", "user:read", "user:write")]

        assert has_permission(roles, "user:read") is True

    def test_denies_when_no_role_has_the_permission(self) -> None:
        roles = [_role("employee", "user:read")]

        assert has_permission(roles, "audit_event:read") is False

    def test_denies_with_no_roles_at_all(self) -> None:
        assert has_permission([], "user:read") is False

    def test_grants_when_any_of_several_roles_has_the_permission(self) -> None:
        roles = [
            _role("employee", "user:read"),
            _role("manager", "user:read", "org:read"),
        ]

        assert has_permission(roles, "org:read") is True


@pytest.mark.unit
class TestHasAnyPermission:
    def test_grants_when_at_least_one_required_permission_is_held(self) -> None:
        roles = [_role("manager", "user:read", "org:read")]

        assert has_any_permission(roles, ["audit_event:read", "org:read"]) is True

    def test_denies_when_none_of_the_required_permissions_are_held(self) -> None:
        roles = [_role("employee", "user:read")]

        assert has_any_permission(roles, ["audit_event:read", "role:assign"]) is False

    def test_denies_with_an_empty_required_list(self) -> None:
        roles = [_role("platform_admin", "user:read", "user:write")]

        assert has_any_permission(roles, []) is False
