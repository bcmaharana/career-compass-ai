"""Exchange a verified Platform Identity token for a normal local
Career Compass AI session.

See docs/adr/ADR-010-platform-identity-integration.md. This is a
one-time handoff, not an ongoing identity provider — CCAI's entire
existing RLS/session machinery (get_tenant_scoped_session,
InternalJWTProvider, verify_access_token) is otherwise completely
untouched; this service's only job is to resolve which CCAI
tenant/user a platform token maps to, then hand off to
InternalJWTProvider.claims_for_user exactly as any other login path
does.

Tenant resolution rule (ADR-010): if the account's active
career_compass_ai entitlement came from a Platform Organization
(entitlement.org_id is set), resolve via Tenant.platform_org_id — an
org not yet linked to a CCAI tenant is a real, honest "not provisioned"
error, not something this service invents a new tenant for. If the
entitlement is direct (org_id is None, the Personal-account case),
resolve via derive_personal_subdomain(email) — creating a brand new
Personal tenant via the existing RegisterTenantService if none exists
yet, the same JIT-provisioning ADR-001 describes.

Which entitlement counts as "the" active one (2026-08-25, multi-scope
accounts): a single Platform account can hold BOTH a direct entitlement
(Personal) and an org-inherited one (Enterprise) for this same product
at once — Platform Identity's claims union both, unfiltered (see
ListMyEntitlementsService on that side). `requested_scope` disambiguates
which one this specific handoff should honor: `None` keeps the original,
pre-multi-scope behavior (take whichever's first — correct and
unambiguous when there's only one, which is still the common case);
`"personal"` requires the direct (org_id is None) one; any other string
is treated as a literal org_id and requires an entitlement matching it
exactly. The platform's own ProductCard.tsx is what actually supplies a
real scope value when there's a genuine choice to make — see that
file's own picker UI.

Deliberately does NOT create a new User in an already-existing,
org-linked tenant when no match is found there: Career Compass AI has
no multi-user-per-tenant invite flow yet (every Enterprise tenant today
has exactly one user — see CLAUDE.md's account-deletion history), so
silently fabricating a second member here would invent app behavior
that doesn't exist anywhere else in this codebase. That case surfaces
as a clear NO_MATCHING_USER error instead.
"""

from __future__ import annotations

import secrets
from uuid import UUID

import phonenumbers

from app.adapters.identity_providers.internal_jwt import InternalJWTProvider
from app.adapters.identity_providers.platform_profile_sync import fetch_platform_profile
from app.adapters.identity_providers.platform_token_verifier import (
    PlatformAccountClaims,
    PlatformEntitlement,
    verify_platform_token,
)
from app.application.identity.audit_service import AuditService
from app.application.identity.dto import LoginResult
from app.application.identity.register_tenant import RegisterTenantService
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.domain.identity.entities import Tenant, User
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.identity.repositories import TenantContextBinder, TenantRepository, UserRepository


def _to_e164(phone_number: str | None, country: str | None) -> str | None:
    """Same permissive, never-raises shape as UpdateUserProfileService's
    own private helper of the same name — duplicated rather than
    imported across modules since that one is deliberately
    module-private."""
    if not phone_number:
        return None
    try:
        parsed = phonenumbers.parse(phone_number, country)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return str(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))


class PlatformHandoffService:
    def __init__(
        self,
        tenants: TenantRepository,
        users: UserRepository,
        tenant_context: TenantContextBinder,
        identity_provider: InternalJWTProvider,
        register_tenant: RegisterTenantService,
        audit: AuditService,
    ) -> None:
        self._tenants = tenants
        self._users = users
        self._tenant_context = tenant_context
        self._identity_provider = identity_provider
        self._register_tenant = register_tenant
        self._audit = audit

    async def execute(
        self, *, platform_token: str, requested_scope: str | None = None
    ) -> LoginResult:
        claims = verify_platform_token(platform_token)

        active_entitlements = [
            e
            for e in claims.entitlements
            if e.product_code == "career_compass_ai" and e.status == "active"
        ]
        ccai_entitlement = self._select_entitlement(active_entitlements, requested_scope)
        if ccai_entitlement is None:
            raise ForbiddenError(
                "This Platform Identity account has no active Career Compass AI "
                "entitlement.",
                code="NO_ENTITLEMENT",
            )

        if ccai_entitlement.org_id is not None:
            tenant = await self._tenants.get_by_platform_org_id(UUID(ccai_entitlement.org_id))
            if tenant is None:
                raise NotFoundError(
                    "This organization has not been linked to a Career Compass AI "
                    "tenant yet.",
                    code="ORG_NOT_PROVISIONED",
                )
            await self._tenant_context.bind(tenant.id)
            user = await self._find_or_link_user(tenant.id, claims)
            if user is None:
                raise NotFoundError(
                    "No matching Career Compass AI user was found for this account "
                    "in this organization's tenant.",
                    code="NO_MATCHING_USER",
                )
        else:
            subdomain = derive_personal_subdomain(claims.email)
            tenant = await self._tenants.get_by_subdomain(subdomain)
            if tenant is not None:
                await self._tenant_context.bind(tenant.id)
                user = await self._find_or_link_user(tenant.id, claims)
                if user is None:
                    raise NotFoundError(
                        "No matching Career Compass AI user was found for this "
                        "account.",
                        code="NO_MATCHING_USER",
                    )
            else:
                tenant, user = await self._create_personal_tenant_and_user(claims, subdomain)

        user = await self._sync_profile_from_platform(user, platform_token)

        identity_claims = await self._identity_provider.claims_for_user(user)
        access_token = self._identity_provider.issue_access_token(identity_claims)

        await self._audit.record(
            tenant_id=tenant.id,
            user_id=user.id,
            action="auth.platform_handoff_success",
            resource_type="user",
            metadata={"platform_account_id": claims.account_id},
        )

        return LoginResult(
            access_token=access_token,
            token_type="bearer",
            user_id=UUID(identity_claims.user_id),
            tenant_id=tenant.id,
            email=identity_claims.email,
            full_name=identity_claims.full_name,
            first_name=identity_claims.first_name,
            last_name=identity_claims.last_name,
            salutation=identity_claims.salutation,
            last_login_at=identity_claims.last_login_at,
            roles=identity_claims.roles,
        )

    @staticmethod
    def _select_entitlement(
        entitlements: list[PlatformEntitlement], requested_scope: str | None
    ) -> PlatformEntitlement | None:
        if not entitlements:
            return None
        if requested_scope is None:
            return entitlements[0]
        if requested_scope == "personal":
            return next((e for e in entitlements if e.org_id is None), None)
        return next((e for e in entitlements if e.org_id == requested_scope), None)

    async def _find_or_link_user(
        self, tenant_id: UUID, claims: PlatformAccountClaims
    ) -> User | None:
        user = await self._users.get_by_platform_account_id(tenant_id, UUID(claims.account_id))
        if user is not None:
            return user

        # Not yet linked by platform_account_id — this is exactly the
        # shape a not-yet-migrated existing user has (real password
        # account, no platform link yet). A plain email match is safe
        # here specifically because we already know (from the caller)
        # which single tenant to look in, so this can never cross a
        # tenant boundary.
        user = await self._users.get_by_email(tenant_id, claims.email)
        if user is None:
            return None
        user.platform_account_id = UUID(claims.account_id)
        return await self._users.update(user)

    async def _sync_profile_from_platform(self, user: User, platform_token: str) -> User:
        """Best-effort — see platform_profile_sync.py's own docstring
        for why a failure here never blocks the handoff itself. Fires on
        every handoff, not just first creation, so a profile edited on
        the Hub shows up here the next time this person re-enters CCAI
        from there."""
        profile = await fetch_platform_profile(platform_token)
        if profile is None:
            return user

        user.salutation = profile.salutation
        user.first_name = profile.first_name
        user.last_name = profile.last_name
        user.middle_name = profile.middle_name
        user.handle = profile.handle
        user.phone_number = profile.phone_number
        user.phone_number_e164 = _to_e164(profile.phone_number, profile.country)
        user.country = profile.country
        user.language = profile.language
        user.address_line1 = profile.address_line1
        user.address_line2 = profile.address_line2
        user.city = profile.city
        user.state = profile.state
        user.postal_code = profile.postal_code
        user.visa_status = profile.visa_status
        user.linkedin_url = profile.linkedin_url
        user.other_professional_url = profile.other_professional_url
        return await self._users.update(user)

    async def _create_personal_tenant_and_user(
        self, claims: PlatformAccountClaims, subdomain: str
    ) -> tuple[Tenant, User]:
        # A platform-authenticated user never needs a local password —
        # generate one that can never be guessed or reused rather than
        # leaving hashed_password blank (it's a required column). This
        # is the same "the platform is the only real login path for
        # this user" outcome ADR-002 describes for the eventual local
        # -login cutover, just realized per-user, from the moment a
        # brand new account is first created via the handoff.
        unusable_password_hash = hash_password(secrets.token_urlsafe(32))

        result = await self._register_tenant.execute_with_hashed_password(
            tenant_name=f"{claims.first_name} {claims.last_name}".strip() or claims.email,
            subdomain=subdomain,
            organization_name="Personal",
            admin_email=claims.email,
            admin_salutation=None,
            admin_first_name=claims.first_name,
            admin_last_name=claims.last_name,
            admin_password_hash=unusable_password_hash,
        )

        tenant = await self._tenants.get_by_id(result.tenant_id)
        assert tenant is not None, "just-created tenant must exist"
        user = await self._users.get_by_id(tenant.id, result.admin_user_id)
        assert user is not None, "just-created user must exist"

        user.platform_account_id = UUID(claims.account_id)
        user = await self._users.update(user)

        return tenant, user
