"""Identity provider abstraction.

See docs/adr/ADR-003-authentication-strategy.md for the rationale.

Application services and API routers depend only on
`IdentityProviderInterface`. Phase 1 implements exactly one concrete
provider (`InternalJWTProvider`, in
`app/adapters/identity_providers/internal_jwt.py`). Future external
providers (Auth0, Okta, Azure Entra ID) implement this same interface
without requiring any change to code that depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    """Normalized identity information, regardless of which provider
    authenticated the caller.

    Every concrete IdentityProviderInterface implementation must return
    claims in this shape, so callers never need to know whether the
    caller authenticated via internal JWT auth or an external OIDC
    provider.
    """

    user_id: str
    tenant_id: str
    email: str
    full_name: str
    first_name: str = ""
    last_name: str = ""
    salutation: str | None = None
    #: The user's *previous* login time (ISO 8601), captured at
    #: authentication before this session's login overwrites it — None on
    #: a user's very first login ever. Deliberately not "this session's
    #: login time" (that's just "now"): a "Last logged in" display is
    #: only meaningful as "when were you last here before now."
    last_login_at: str | None = None
    roles: tuple[str, ...] = ()


class IdentityProviderInterface(Protocol):
    """Contract every authentication provider must implement."""

    async def authenticate_with_credentials(
        self, *, email: str, password: str, tenant_id: str
    ) -> IdentityClaims:
        """Authenticate a user via email/password within a given tenant.

        Raises app.core.exceptions.UnauthorizedError on failure.
        """
        ...

    async def verify_token(self, *, token: str) -> IdentityClaims:
        """Verify an access token and return the identity it represents.

        Raises app.core.exceptions.UnauthorizedError if the token is
        missing, malformed, expired, or otherwise invalid.
        """
        ...
