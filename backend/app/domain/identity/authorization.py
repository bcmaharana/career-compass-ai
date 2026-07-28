"""Pure RBAC authorization logic.

Takes the roles already resolved for a user (with their permission codes
attached) and answers "is this permission granted" — no database access,
no HTTP concepts. This is what makes authorization logic unit-testable
without spinning up Postgres: see tests/unit/test_authorization.py.
"""

from __future__ import annotations

from app.domain.identity.entities import Role


def has_permission(roles: list[Role], required_permission_code: str) -> bool:
    """Return True if any of the given roles grants the required permission."""
    return any(required_permission_code in role.permission_codes for role in roles)


def has_any_permission(roles: list[Role], required_permission_codes: list[str]) -> bool:
    """Return True if any of the given roles grants at least one of the
    required permissions."""
    granted = {code for role in roles for code in role.permission_codes}
    return any(code in granted for code in required_permission_codes)
