"""Verifies a Platform Identity account-deletion assertion — the
counterpart to platform_token_verifier.py's session-token verification,
same RS256 keypair, different purpose.

Deliberately narrow: proves the signature and that this token was
minted specifically for account deletion (not a reused session/handoff
token), nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


@dataclass(frozen=True, slots=True)
class PlatformDeletionAssertion:
    account_id: str
    email: str
    #: None for a Personal account; set to the Hub Organization's id for
    #: an Enterprise account — lets PlatformAccountDeletionService
    #: resolve the tenant via Tenant.platform_org_id (the same lookup
    #: PlatformHandoffService already uses at handoff time) instead of
    #: only ever guessing a Personal subdomain from the email.
    org_id: str | None


def verify_platform_deletion_assertion(token: str) -> PlatformDeletionAssertion:
    settings = get_settings()
    if not settings.platform_identity_public_key_pem:
        raise UnauthorizedError(
            "Platform Identity handoff is not configured for this deployment.",
            code="PLATFORM_HANDOFF_NOT_CONFIGURED",
        )

    try:
        payload = jwt.decode(
            token, settings.platform_identity_public_key_pem, algorithms=["RS256"]
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(
            "Invalid or expired platform token.", code="INVALID_PLATFORM_TOKEN"
        ) from exc

    if payload.get("purpose") != "account_deletion":
        raise UnauthorizedError(
            "This token was not issued for account deletion.", code="INVALID_PLATFORM_TOKEN"
        )

    return PlatformDeletionAssertion(
        account_id=payload["sub"], email=payload["email"], org_id=payload.get("org_id")
    )
