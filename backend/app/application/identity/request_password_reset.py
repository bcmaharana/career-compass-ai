"""Request a password reset (the "forgot password" step).

Requires the caller to know which tenant they're in (by subdomain), the
same reasoning AuthenticateUserService documents for login — users are
scoped per tenant and RLS needs a tenant context bound before the user
lookup runs.

Always returns the same generic outcome regardless of whether the
subdomain/email combination is real — mirrors AuthenticateUserService's
"same error whether the subdomain or the password was wrong" principle,
inverted to identical *success*, so this endpoint can never be used to
enumerate which email addresses have accounts.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.application.identity.audit_service import AuditService
from app.core.email_provider_interface import EmailMessage, EmailProviderInterface
from app.core.exceptions import CareerCompassError
from app.core.logging import get_logger
from app.domain.identity.entities import PasswordResetToken
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import (
    PasswordResetTokenRepository,
    TenantContextBinder,
    TenantRepository,
    UserRepository,
)

logger = get_logger(__name__)

RESET_TOKEN_TTL = timedelta(minutes=30)


class RequestPasswordResetService:
    def __init__(
        self,
        tenants: TenantRepository,
        users: UserRepository,
        reset_tokens: PasswordResetTokenRepository,
        tenant_context: TenantContextBinder,
        email_provider: EmailProviderInterface,
        audit: AuditService,
        frontend_base_url: str,
    ) -> None:
        self._tenants = tenants
        self._users = users
        self._reset_tokens = reset_tokens
        self._tenant_context = tenant_context
        self._email_provider = email_provider
        self._audit = audit
        self._frontend_base_url = frontend_base_url.rstrip("/")

    async def execute(self, *, subdomain: str | None, email: str) -> None:
        # Same "blank means Personal account" convention as
        # AuthenticateUserService.execute — recomputes the deterministic
        # subdomain rather than requiring one from a user who was never
        # asked for one at signup or login either.
        resolved_subdomain = subdomain or derive_personal_subdomain(email)
        tenant = await self._tenants.get_by_subdomain(resolved_subdomain)
        if tenant is None:
            return

        await self._tenant_context.bind(tenant.id)

        user = await self._users.get_by_email(tenant.id, email)
        if user is None or not user.is_active:
            return

        await self._reset_tokens.invalidate_unused_for_user(tenant.id, user.id)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(UTC)
        await self._reset_tokens.create(
            PasswordResetToken(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=user.id,
                token_hash=token_hash,
                expires_at=now + RESET_TOKEN_TTL,
                used_at=None,
                created_at=now,
            )
        )

        reset_link = f"{self._frontend_base_url}/reset-password?token={raw_token}"
        try:
            await self._email_provider.send_email(
                EmailMessage(
                    to=user.email,
                    subject="Reset your Career Compass AI password",
                    html_body=(
                        f"<p>Hi {user.first_name},</p>"
                        "<p>We received a request to reset your Career Compass AI "
                        "password. This link expires in 30 minutes:</p>"
                        f'<p><a href="{reset_link}">{reset_link}</a></p>'
                        "<p>If you didn't request this, you can safely ignore this "
                        "email.</p>"
                    ),
                )
            )
        except CareerCompassError:
            # A provider outage must not turn into a 500 (which would
            # reveal, via response shape/timing, that a real account was
            # found) — log and swallow, the caller still gets the
            # identical generic response either way.
            logger.warning(
                "password_reset_email_failed", tenant_id=str(tenant.id), user_id=str(user.id)
            )
            return

        await self._audit.record(
            tenant_id=tenant.id,
            user_id=user.id,
            action="password_reset.requested",
            resource_type="user",
        )
