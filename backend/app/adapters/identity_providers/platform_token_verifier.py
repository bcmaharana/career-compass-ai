"""Verifies the signature on a Platform Identity RS256 token — the
Career Compass AI side of the federated-identity handoff.

See the sibling `enterprise/platform` repo's
docs/adr/ADR-001-federated-identity-platform.md for the platform-side
design, and this repo's own
docs/adr/ADR-010-platform-identity-integration.md for how the two sides
meet.

This deliberately does NOT implement IdentityProviderInterface — that
contract returns this app's own tenant-scoped IdentityClaims, but a
Platform Identity token carries no notion of a CCAI tenant at all
(resolving that is exactly what PlatformHandoffService does). This is a
narrower, one-purpose verifier: prove the token's signature and shape,
nothing more. It's only ever used once per browser session, to
bootstrap a normal local CCAI session — every request after that goes
through CCAI's own locally-issued JWT via the existing
InternalJWTProvider/verify_access_token path, completely unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


@dataclass(frozen=True, slots=True)
class PlatformOrgMembership:
    org_id: str
    org_name: str
    role: str


@dataclass(frozen=True, slots=True)
class PlatformEntitlement:
    product_code: str
    status: str
    #: Which Platform Organization granted this entitlement, if any —
    #: None means it was granted directly to the account (the Personal
    #: -tenant case). PlatformHandoffService uses this to decide whether
    #: to resolve a CCAI tenant via platform_org_id or via the
    #: account's own derive_personal_subdomain(email).
    org_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformAccountClaims:
    account_id: str
    email: str
    first_name: str
    last_name: str
    is_platform_admin: bool
    orgs: tuple[PlatformOrgMembership, ...]
    entitlements: tuple[PlatformEntitlement, ...]


def verify_platform_token(token: str) -> PlatformAccountClaims:
    """Raises UnauthorizedError if the handoff isn't configured, or if
    the token is missing, malformed, expired, or has an invalid
    signature."""
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

    return PlatformAccountClaims(
        account_id=payload["sub"],
        email=payload["email"],
        first_name=payload.get("first_name", ""),
        last_name=payload.get("last_name", ""),
        is_platform_admin=payload.get("is_platform_admin", False),
        orgs=tuple(PlatformOrgMembership(**org) for org in payload.get("orgs", [])),
        entitlements=tuple(
            PlatformEntitlement(**entitlement) for entitlement in payload.get("entitlements", [])
        ),
    )
