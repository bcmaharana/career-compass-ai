"""Authenticate a user (login).

Requires the caller to know which tenant they're logging into (by
subdomain) since users are scoped per tenant and RLS needs a tenant
context bound before the user lookup runs. This mirrors real-world
multi-tenant login UX: a user typically reaches a tenant-specific login
URL (e.g. acme.careercompass.ai/login) rather than a single global login
page.
"""

from __future__ import annotations

from uuid import UUID

from app.adapters.identity_providers.firebase_phone import FirebasePhoneVerifier
from app.adapters.identity_providers.internal_jwt import InternalJWTProvider
from app.application.identity.audit_service import AuditService
from app.application.identity.dto import LoginResult
from app.core.exceptions import UnauthorizedError
from app.domain.identity.repositories import TenantContextBinder, TenantRepository


class AuthenticateUserService:
    def __init__(
        self,
        tenants: TenantRepository,
        tenant_context: TenantContextBinder,
        identity_provider: InternalJWTProvider,
        audit: AuditService,
        phone_verifier: FirebasePhoneVerifier | None = None,
    ) -> None:
        self._tenants = tenants
        self._tenant_context = tenant_context
        self._identity_provider = identity_provider
        self._audit = audit
        # None until Firebase phone login is configured (see
        # app/api/dependencies.py's get_firebase_phone_verifier) — kept
        # optional here rather than making every caller of this service's
        # constructor (tests included) provide a live Firebase adapter
        # just to exercise the unrelated email/password path.
        self._phone_verifier = phone_verifier

    async def execute(self, *, subdomain: str, email: str, password: str) -> LoginResult:
        tenant = await self._tenants.get_by_subdomain(subdomain)
        if tenant is None:
            # Deliberately the same error as a bad password would produce
            # — do not reveal whether a subdomain exists.
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")

        await self._tenant_context.bind(tenant.id)

        try:
            claims = await self._identity_provider.authenticate_with_credentials(
                email=email, password=password, tenant_id=str(tenant.id)
            )
        except UnauthorizedError:
            await self._audit.record(
                tenant_id=tenant.id,
                action="auth.login_failure",
                resource_type="user",
                metadata={"email": email},
            )
            raise

        access_token = self._identity_provider.issue_access_token(claims)

        await self._audit.record(
            tenant_id=tenant.id,
            user_id=UUID(claims.user_id),
            action="auth.login_success",
            resource_type="user",
            metadata={"email": email},
        )

        return LoginResult(
            access_token=access_token,
            token_type="bearer",
            user_id=UUID(claims.user_id),
            tenant_id=tenant.id,
            email=claims.email,
            full_name=claims.full_name,
            first_name=claims.first_name,
            last_name=claims.last_name,
            salutation=claims.salutation,
            last_login_at=claims.last_login_at,
            roles=claims.roles,
        )

    async def execute_phone(self, *, subdomain: str, firebase_id_token: str) -> LoginResult:
        """Phone login: the frontend already completed the actual OTP
        challenge with Firebase directly (see frontend/src/lib/firebase.ts)
        and hands us the resulting ID token. Firebase proved the caller
        controls the phone number; this just maps that verified number to
        a Career Compass user within the given tenant and issues our own
        JWT, the same as execute() does after a password check.
        """
        if self._phone_verifier is None:
            raise UnauthorizedError(
                "Phone login is not configured for this deployment.",
                code="PHONE_LOGIN_NOT_CONFIGURED",
            )

        tenant = await self._tenants.get_by_subdomain(subdomain)
        if tenant is None:
            # Same "don't reveal whether a subdomain exists" reasoning as
            # execute() — an invalid subdomain and an unrecognized phone
            # number must be indistinguishable to the caller.
            raise UnauthorizedError(
                "Invalid phone number or code.", code="INVALID_CREDENTIALS"
            )

        await self._tenant_context.bind(tenant.id)

        # Deliberately outside the try/except below: a bad/expired
        # Firebase token is a different failure than "we don't recognize
        # this phone number" and isn't a login attempt against a real
        # account yet, so it isn't audit-logged as one.
        phone_e164 = self._phone_verifier.verify_phone_number(firebase_id_token)

        try:
            claims = await self._identity_provider.authenticate_with_phone(
                phone_e164=phone_e164, tenant_id=str(tenant.id)
            )
        except UnauthorizedError:
            await self._audit.record(
                tenant_id=tenant.id,
                action="auth.login_failure",
                resource_type="user",
                metadata={"phone_number": phone_e164, "method": "phone"},
            )
            raise

        access_token = self._identity_provider.issue_access_token(claims)

        await self._audit.record(
            tenant_id=tenant.id,
            user_id=UUID(claims.user_id),
            action="auth.login_success",
            resource_type="user",
            metadata={"phone_number": phone_e164, "method": "phone"},
        )

        return LoginResult(
            access_token=access_token,
            token_type="bearer",
            user_id=UUID(claims.user_id),
            tenant_id=tenant.id,
            email=claims.email,
            full_name=claims.full_name,
            first_name=claims.first_name,
            last_name=claims.last_name,
            salutation=claims.salutation,
            last_login_at=claims.last_login_at,
            roles=claims.roles,
        )
