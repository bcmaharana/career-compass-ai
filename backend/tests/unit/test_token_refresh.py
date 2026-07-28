"""Unit tests for the sliding-session token refresh logic.

See app/api/dependencies.py's get_current_identity docstring for the
design: a token past the halfway point of its configured lifetime gets
silently reissued via the X-Refreshed-Token response header, so active
use keeps extending the session while genuine idle time still expires it
on schedule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Response

from app.api.dependencies import _refresh_token_if_stale
from app.core.config import get_settings
from app.core.identity_provider_interface import IdentityClaims


def _make_token(*, issued_at: datetime) -> str:
    """Builds a token with an explicit iat — create_access_token always
    uses "now", so a test that needs an *old* token has to construct one
    directly with the same secret/algorithm the app itself uses.
    """
    settings = get_settings()
    payload = {
        "sub": "user-1",
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "tenant_id": "tenant-1",
        "email": "test@example.com",
        "roles": ["employee"],
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _identity() -> IdentityClaims:
    return IdentityClaims(
        user_id="user-1",
        tenant_id="tenant-1",
        email="test@example.com",
        full_name="Test User",
        first_name="Test",
        last_name="User",
        salutation="Dr.",
        last_login_at="2026-07-20T10:00:00+00:00",
        roles=("employee",),
    )


@pytest.mark.unit
class TestSlidingSessionRefresh:
    def test_fresh_token_is_not_refreshed(self) -> None:
        token = _make_token(issued_at=datetime.now(UTC))
        response = Response()

        _refresh_token_if_stale(token, _identity(), response)

        assert "X-Refreshed-Token" not in response.headers

    def test_token_past_half_life_is_refreshed(self) -> None:
        settings = get_settings()
        half_life = timedelta(minutes=settings.jwt_access_token_expire_minutes / 2)
        # Comfortably past the halfway point, but still short of expiry.
        issued_at = datetime.now(UTC) - half_life - timedelta(minutes=1)
        token = _make_token(issued_at=issued_at)
        response = Response()

        _refresh_token_if_stale(token, _identity(), response)

        assert "X-Refreshed-Token" in response.headers
        new_token = response.headers["X-Refreshed-Token"]
        assert new_token != token

        # The reissued token should carry the same identity forward.
        decoded = jwt.decode(
            new_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert decoded["sub"] == "user-1"
        assert decoded["tenant_id"] == "tenant-1"
        assert decoded["roles"] == ["employee"]
        # Regression check: a refreshed token must carry first_name/
        # last_name forward too, not just full_name — these were added
        # to the claims after full_name already existed, and the refresh
        # path had to be updated separately to not silently drop them.
        assert decoded["first_name"] == "Test"
        assert decoded["last_name"] == "User"
        assert decoded["salutation"] == "Dr."
        assert decoded["last_login_at"] == "2026-07-20T10:00:00+00:00"

    def test_token_just_under_half_life_is_not_yet_refreshed(self) -> None:
        settings = get_settings()
        half_life = timedelta(minutes=settings.jwt_access_token_expire_minutes / 2)
        issued_at = datetime.now(UTC) - half_life + timedelta(minutes=1)
        token = _make_token(issued_at=issued_at)
        response = Response()

        _refresh_token_if_stale(token, _identity(), response)

        assert "X-Refreshed-Token" not in response.headers
