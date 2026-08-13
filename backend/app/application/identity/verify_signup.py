"""Confirm a signup (the "click the emailed link" step) — creates the
real Tenant/Organization/User for the first time and immediately mints
a session, so a verified signup lands the person straight in the app
rather than making them log in separately right after.

Can be specific about invalid/expired tokens, same reasoning as
ResetPasswordService — the token is unguessable, no enumeration risk.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.adapters.identity_providers.internal_jwt import InternalJWTProvider
from app.application.identity.dto import LoginResult
from app.application.identity.register_tenant import RegisterTenantService
from app.core.email_provider_interface import EmailMessage, EmailProviderInterface
from app.core.exceptions import CareerCompassError, UnauthorizedError
from app.core.logging import get_logger
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import PendingSignupRepository, UserRepository

logger = get_logger(__name__)


class VerifySignupService:
    def __init__(
        self,
        pending_signups: PendingSignupRepository,
        register_tenant: RegisterTenantService,
        users: UserRepository,
        identity_provider: InternalJWTProvider,
        email_provider: EmailProviderInterface,
        welcome_from_email: str,
    ) -> None:
        self._pending_signups = pending_signups
        self._register_tenant = register_tenant
        self._users = users
        self._identity_provider = identity_provider
        self._email_provider = email_provider
        self._welcome_from_email = welcome_from_email

    async def execute(self, *, token: str) -> LoginResult:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        pending = await self._pending_signups.get_by_token_hash(token_hash)
        if pending is None or pending.expires_at < datetime.now(UTC):
            raise UnauthorizedError(
                "This verification link is invalid or has expired.",
                code="INVALID_SIGNUP_TOKEN",
            )

        if pending.kind == "enterprise":
            assert pending.tenant_name and pending.subdomain and pending.organization_name, (
                "enterprise pending signups must have tenant_name/subdomain/organization_name"
            )
            tenant_name = pending.tenant_name
            subdomain = pending.subdomain
            organization_name = pending.organization_name
        else:
            tenant_name = f"{pending.first_name} {pending.last_name}"
            subdomain = derive_personal_subdomain(pending.email)
            organization_name = "Personal"

        result = await self._register_tenant.execute_with_hashed_password(
            tenant_name=tenant_name,
            subdomain=subdomain,
            organization_name=organization_name,
            admin_email=pending.email,
            admin_salutation=None,
            admin_first_name=pending.first_name,
            admin_last_name=pending.last_name,
            admin_password_hash=pending.hashed_password,
            agreed_to_terms_at=pending.agreed_to_terms_at,
            terms_version=pending.terms_version,
        )

        await self._pending_signups.delete(pending.id)

        # Best-effort: the account already exists at this point, so a
        # provider outage here must not block login the way a failed
        # verification-link send blocks signup itself.
        try:
            await self._email_provider.send_email(
                EmailMessage(
                    to=pending.email,
                    subject="Welcome to Career Compass AI!",
                    html_body=(
                        f"<p>Hi {pending.first_name},</p>"
                        "<p>Your Career Compass AI account is ready. We're excited to "
                        "help you build your career profile and plan your next move.</p>"
                        "<p>Log in any time to pick up where you left off.</p>"
                    ),
                    from_email=self._welcome_from_email,
                )
            )
        except CareerCompassError:
            logger.warning("welcome_email_failed", email=pending.email)

        user = await self._users.get_by_id(result.tenant_id, result.admin_user_id)
        assert user is not None, "just-created user must exist"

        claims = await self._identity_provider.claims_for_user(user)
        access_token = self._identity_provider.issue_access_token(claims)

        return LoginResult(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            tenant_id=result.tenant_id,
            email=claims.email,
            full_name=claims.full_name,
            first_name=claims.first_name,
            last_name=claims.last_name,
            salutation=claims.salutation,
            last_login_at=claims.last_login_at,
            roles=claims.roles,
        )
