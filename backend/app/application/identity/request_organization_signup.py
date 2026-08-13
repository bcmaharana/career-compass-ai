"""Request an Enterprise (organization) signup — step 1 of 2.

Same two-phase shape as request_personal_signup.py, just with the
user-chosen tenant_name/subdomain/organization_name carried through the
pending_signups row instead of computed server-side.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from app.application.identity.request_personal_signup import SIGNUP_TOKEN_TTL
from app.core.email_provider_interface import EmailMessage, EmailProviderInterface
from app.core.exceptions import CareerCompassError, ConflictError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.identity.entities import PendingSignup
from app.domain.identity.legal_terms import CURRENT_TERMS_VERSION
from app.domain.identity.repositories import PendingSignupRepository, TenantRepository

logger = get_logger(__name__)


class RequestOrganizationSignupService:
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
        tenant_name: str,
        subdomain: str,
        organization_name: str,
        admin_email: str,
        admin_password: str,
        admin_first_name: str,
        admin_last_name: str,
    ) -> None:
        if await self._tenants.get_by_subdomain(subdomain) is not None:
            raise ConflictError(
                f"Subdomain '{subdomain}' is already in use.", code="SUBDOMAIN_TAKEN"
            )

        await self._pending_signups.delete_all_for_email(admin_email)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(UTC)
        await self._pending_signups.create(
            PendingSignup(
                id=uuid.uuid4(),
                kind="enterprise",
                email=admin_email,
                hashed_password=hash_password(admin_password),
                first_name=admin_first_name,
                last_name=admin_last_name,
                tenant_name=tenant_name,
                subdomain=subdomain,
                organization_name=organization_name,
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
                    to=admin_email,
                    subject="Verify your email for Career Compass AI",
                    html_body=(
                        f"<p>Hi {admin_first_name},</p>"
                        f"<p>Confirm your email to finish setting up {tenant_name} on "
                        "Career Compass AI. This link expires in 60 minutes:</p>"
                        f'<p><a href="{verify_link}">{verify_link}</a></p>'
                        "<p>If you didn't request this, you can safely ignore this "
                        "email.</p>"
                    ),
                    from_email=self._from_email,
                )
            )
        except CareerCompassError:
            logger.warning("signup_verification_email_failed", email=admin_email)
            raise
