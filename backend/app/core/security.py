"""Security primitives: password hashing and JWT token utilities.

These are low-level building blocks used by the Phase 1
`InternalJWTProvider` (see `docs/adr/ADR-003-authentication-strategy.md`).
Nothing in this module knows about users, tenants, or HTTP — it only knows
how to hash a password and how to encode/decode a token.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return str(_pwd_context.hash(plain_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    return bool(_pwd_context.verify(plain_password, hashed_password))


def create_access_token(
    *,
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    `subject` is typically the user's UUID. `extra_claims` carries things
    like tenant_id and roles once Phase 1's identity model exists.
    """
    settings = get_settings()
    expire_delta = expires_delta or timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expire_delta,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises jwt.PyJWTError (or a subclass) if the token is invalid or
    expired — callers in the auth middleware are responsible for
    translating that into an UnauthorizedError.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
