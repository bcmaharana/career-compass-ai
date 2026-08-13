"""Request a Personal (no-organization-needed) signup — step 1 of 2.

Nothing is written to tenants/organizations/users here — only a
pending_signups row. The account only actually gets created once the
emailed verification link is confirmed (see verify_signup.py). Reuses
the exact "opaque token, only its hash stored, email the raw token in a
link" pattern request_password_reset.py already established.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.core.email_provider_interface import EmailMessage, EmailProviderInterface
from app.core.exceptions import CareerCompassError, ConflictError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.identity.entities import PendingSignup
from app.domain.identity.legal_terms import CURRENT_TERMS_VERSION
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import PendingSignupRepository, TenantRepository

logger = get_logger(__name__)

SIGNUP_TOKEN_TTL = timedelta(minutes=60)


class RequestPersonalSignupService:
    def __init__(
        self,
        tenants: TenantRepository,
        pending_signups: PendingSignupRepository,
        email_provider: EmailProviderInterface,
        frontend_base_url: str,
        from_email: str,
    ) -> None:
        self._tenants = tenants
        self._pending_signups = pending_signups
        self._email_provider = email_provider
        self._frontend_base_url = frontend_base_url.rstrip("/")
        self._from_email = from_email

    async def execute(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> None:
        # Immediate, specific rejection (not deferred to confirm time) —
        # matches this app's existing signup UX, where a duplicate is
        # reported right away, unlike the deliberately-generic
        # password-reset-request flow.
        if await self._tenants.get_by_subdomain(derive_personal_subdomain(email)) is not None:
            raise ConflictError(
                "An account with this email already exists.", code="EMAIL_ALREADY_REGISTERED"
            )

        await self._pending_signups.delete_all_for_email(email)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(UTC)
        await self._pending_signups.create(
            PendingSignup(
                id=uuid.uuid4(),
                kind="personal",
                email=email,
                hashed_password=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                tenant_name=None,
                subdomain=None,
                organization_name=None,
                token_hash=token_hash,
                expires_at=now + SIGNUP_TOKEN_TTL,
                created_at=now,
                agreed_to_terms_at=now,
                terms_version=CURRENT_TERMS_VERSION,
            )
        )

        verify_link = f"{self._frontend_base_url}/verify-email?token={raw_token}"
        try:
            await self._email_provider.send_email(
                EmailMessage(
                    to=email,
                    subject="Verify your email for Career Compass AI",
                    html_body=(
                        f"<p>Hi {first_name},</p>"
                        "<p>Confirm your email to finish creating your Career Compass AI "
                        "account. This link expires in 60 minutes:</p>"
                        f'<p><a href="{verify_link}">{verify_link}</a></p>'
                        "<p>If you didn't request this, you can safely ignore this "
                        "email.</p>"
                    ),
                    from_email=self._from_email,
                )
            )
        except CareerCompassError:
            logger.warning("signup_verification_email_failed", email=email)
            raise
