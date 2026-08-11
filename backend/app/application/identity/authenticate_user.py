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
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import (
    PersonalPhoneLoginRepository,
    TenantContextBinder,
    TenantRepository,
)


class AuthenticateUserService:
    def __init__(
        self,
        tenants: TenantRepository,
        tenant_context: TenantContextBinder,
        identity_provider: InternalJWTProvider,
        audit: AuditService,
        phone_verifier: FirebasePhoneVerifier | None = None,
        personal_phone_logins: PersonalPhoneLoginRepository | None = None,
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
        # Only needed for Personal (subdomain-less) phone login's
        # cross-tenant lookup — None is fine whenever phone_verifier is
        # also None, and every real wiring provides both together (see
        # app/api/dependencies.py's get_authenticate_user_service).
        self._personal_phone_logins = personal_phone_logins

    async def execute(
        self, *, subdomain: str | None, email: str, password: str
    ) -> LoginResult:
        # A blank/omitted subdomain means "Personal account" — the
        # frontend never asks a Personal user for one, at signup or at
        # login, so this recomputes the same deterministic lookup key
        # PersonalSignupService derived when the account was created.
        resolved_subdomain = subdomain or derive_personal_subdomain(email)
        tenant = await self._tenants.get_by_subdomain(resolved_subdomain)
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

    async def execute_phone(
        self, *, subdomain: str | None, firebase_id_token: str
    ) -> LoginResult:
        """Phone login: the frontend already completed the actual OTP
        challenge with Firebase directly (see frontend/src/lib/firebase.ts)
        and hands us the resulting ID token. Firebase proved the caller
        controls the phone number; this just maps that verified number to
        a Career Compass user and issues our own JWT, the same as
        execute() does after a password check.

        A blank/omitted subdomain means "Personal account" — the same
        convention execute() uses for email/password login. Unlike
        email, a phone number can't be hashed into a deterministic
        subdomain (it isn't known at signup time, only added later via
        Settings > Profile), so Personal phone login resolves the tenant
        through personal_phone_logins, a small RLS-exempt cross-tenant
        lookup populated by UpdateUserProfileService whenever a Personal
        user saves a phone number — see that table's migration for the
        full reasoning.
        """
        if self._phone_verifier is None:
            raise UnauthorizedError(
                "Phone login is not configured for this deployment.",
                code="PHONE_LOGIN_NOT_CONFIGURED",
            )

        # Verified first, before any tenant resolution — it's
        # independent of which tenant is involved, and Personal login
        # needs the phone number in hand before it can even look up a
        # tenant (unlike Enterprise, which already has the subdomain).
        # A bad/expired Firebase token is a different failure than "we
        # don't recognize this phone number" and isn't a login attempt
        # against a real account yet, so it isn't audit-logged as one.
        phone_e164 = self._phone_verifier.verify_phone_number(firebase_id_token)

        if subdomain:
            tenant = await self._tenants.get_by_subdomain(subdomain)
        elif self._personal_phone_logins is not None:
            resolved_tenant_id = await self._personal_phone_logins.get_tenant_id(phone_e164)
            tenant = (
                await self._tenants.get_by_id(resolved_tenant_id)
                if resolved_tenant_id is not None
                else None
            )
        else:
            tenant = None

        if tenant is None:
            # Same "don't reveal whether a subdomain/number exists"
            # reasoning as execute() — an invalid subdomain, an
            # unrecognized phone number, and an unregistered Personal
            # number must all be indistinguishable to the caller.
            raise UnauthorizedError(
                "Invalid phone number or code.", code="INVALID_CREDENTIALS"
            )

        await self._tenant_context.bind(tenant.id)

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
