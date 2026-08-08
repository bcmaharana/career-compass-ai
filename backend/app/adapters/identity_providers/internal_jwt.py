"""Internal JWT authentication provider.

The one concrete implementation of IdentityProviderInterface shipped in
Phase 1 (see docs/adr/ADR-003-authentication-strategy.md). External SSO
providers (Auth0, Okta, Azure Entra ID) will implement the same interface
later without requiring any change to callers of
IdentityProviderInterface.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import jwt

from app.core.exceptions import UnauthorizedError
from app.core.identity_provider_interface import IdentityClaims
from app.core.security import create_access_token, decode_access_token, verify_password
from app.domain.identity.repositories import RoleRepository, UserRepository


def verify_access_token(token: str) -> IdentityClaims:
    """Decode and verify a JWT access token, with no dependency on any
    repository — this is what makes token verification usable directly
    from the API-layer auth dependency without constructing a full
    InternalJWTProvider (which needs repositories only its credential
    -based login path uses).
    """
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token.", code="INVALID_TOKEN") from exc

    return IdentityClaims(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        email=payload["email"],
        # .get() with a fallback, unlike email/tenant_id/roles above:
        # full_name/first_name/last_name were added to the token schema
        # after tokens without them were already in circulation, so an
        # old still-valid token must not fail verification just because
        # it predates these claims.
        full_name=payload.get("full_name") or "",
        first_name=payload.get("first_name") or "",
        last_name=payload.get("last_name") or "",
        salutation=payload.get("salutation"),
        last_login_at=payload.get("last_login_at"),
        roles=tuple(payload.get("roles", ())),
    )


class InternalJWTProvider:
    """Email/password authentication backed by the local User table,
    issuing JWT access tokens. Implements IdentityProviderInterface.
    """

    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def authenticate_with_credentials(
        self, *, email: str, password: str, tenant_id: str
    ) -> IdentityClaims:
        user = await self._users.get_by_email(UUID(tenant_id), email)
        if user is None or not user.is_active:
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")

        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")

        roles = await self._roles.list_for_user(user.tenant_id, user.id)
        role_names = tuple(role.name for role in roles)

        # Capture the *previous* login time before overwriting it — "Last
        # logged in" only means something as "before this session."
        previous_login_at = user.last_login_at.isoformat() if user.last_login_at else None
        user.last_login_at = datetime.now(UTC)
        await self._users.update(user)

        return IdentityClaims(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            full_name=user.display_name,
            first_name=user.first_name,
            last_name=user.last_name,
            salutation=user.salutation,
            last_login_at=previous_login_at,
            roles=role_names,
        )

    async def authenticate_with_phone(self, *, phone_e164: str, tenant_id: str) -> IdentityClaims:
        """Phone login's counterpart to authenticate_with_credentials — no
        password check here because proof of phone ownership already
        happened at the Firebase layer (see
        app/adapters/identity_providers/firebase_phone.py and
        AuthenticateUserService.execute_phone); this only has to find the
        matching user and mint the same IdentityClaims shape either login
        path produces.
        """
        user = await self._users.get_by_phone_e164(UUID(tenant_id), phone_e164)
        if user is None or not user.is_active:
            raise UnauthorizedError(
                "Invalid phone number or code.", code="INVALID_CREDENTIALS"
            )

        roles = await self._roles.list_for_user(user.tenant_id, user.id)
        role_names = tuple(role.name for role in roles)

        previous_login_at = user.last_login_at.isoformat() if user.last_login_at else None
        user.last_login_at = datetime.now(UTC)
        await self._users.update(user)

        return IdentityClaims(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            full_name=user.display_name,
            first_name=user.first_name,
            last_name=user.last_name,
            salutation=user.salutation,
            last_login_at=previous_login_at,
            roles=role_names,
        )

    async def verify_token(self, *, token: str) -> IdentityClaims:
        return verify_access_token(token)

    def issue_access_token(self, claims: IdentityClaims) -> str:
        """Not part of IdentityProviderInterface — a provider-specific
        helper the login application service calls after successful
        authentication to mint the token returned to the client.
        """
        return create_access_token(
            subject=claims.user_id,
            extra_claims={
                "tenant_id": claims.tenant_id,
                "email": claims.email,
                "full_name": claims.full_name,
                "first_name": claims.first_name,
                "last_name": claims.last_name,
                "salutation": claims.salutation,
                "last_login_at": claims.last_login_at,
                "roles": list(claims.roles),
            },
        )
