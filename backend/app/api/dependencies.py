"""Shared FastAPI dependencies: database sessions, current identity
resolution, and RBAC enforcement.

This module is the seam between "framework" and "everything else" — it's
where concrete adapters (SQLAlchemy sessions, the InternalJWTProvider)
get wired into application services via Depends(), so application
services themselves only ever see interfaces (see
docs/architecture/backend-architecture.md, "Dependency Injection").
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ai_providers.anthropic_provider import AnthropicProvider
from app.adapters.ai_providers.groq_provider import GroqProvider
from app.adapters.ai_providers.ollama_embedding_provider import OllamaEmbeddingProvider
from app.adapters.ai_providers.ollama_provider import OllamaProvider
from app.adapters.db.account_deletion import SqlAlchemyAccountDeletionRepository
from app.adapters.db.base import async_session_factory, set_tenant_context
from app.adapters.db.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyCareerGoalRepository,
    SqlAlchemyCareerHighlightRepository,
    SqlAlchemyCareerProfileRepository,
    SqlAlchemyCertificationRepository,
    SqlAlchemyEducationRepository,
    SqlAlchemyExperienceRepository,
    SqlAlchemyFeatureFlagRepository,
    SqlAlchemyKeyAchievementRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyPeerEndorsementRepository,
    SqlAlchemyPendingSignupRepository,
    SqlAlchemyPersonalPhoneLoginRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyTargetRoleRepository,
    SqlAlchemyTenantContextBinder,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.adapters.db.repositories.ai_platform import (
    SqlAlchemyInvocationLogger,
    SqlAlchemyModelRegistry,
    SqlAlchemyPromptRegistry,
)
from app.adapters.db.repositories.career_intelligence import (
    SqlAlchemyCategoryParentRepository,
    SqlAlchemyCikgRoleRepository,
    SqlAlchemyCompetencyRepository,
    SqlAlchemyPrerequisiteOfEdgeRepository,
    SqlAlchemyRelatedSkillRepository,
    SqlAlchemyRoleRequiredSkillRepository,
    SqlAlchemySkillAliasRepository,
    SqlAlchemySkillCategoryMembershipRepository,
    SqlAlchemySkillCategoryRepository,
    SqlAlchemySkillCompetencyMembershipRepository,
    SqlAlchemySkillRepository,
    SqlAlchemySpecializesEdgeRepository,
    SqlAlchemySynonymOfEdgeRepository,
)
from app.adapters.db.repositories.career_profile import SqlAlchemyCareerProfileVersionRepository
from app.adapters.db.repositories.chat import (
    SqlAlchemyChatConversationRepository,
    SqlAlchemyChatMessageRepository,
)
from app.adapters.db.repositories.governance import (
    SqlAlchemyContentHistoryRepository,
    SqlAlchemyContentRevisionRepository,
)
from app.adapters.db.repositories.platform_admin import (
    SqlAlchemyPlatformAdminRepository,
    SqlAlchemyPlatformSettingsRepository,
)
from app.adapters.db.repositories.resume_intelligence import SqlAlchemyResumeRepository
from app.adapters.email.resend_provider import ResendEmailProvider
from app.adapters.db.repositories.search import (
    SqlAlchemyContentEmbeddingRepository,
    SqlAlchemyEmbeddingModelRepository,
    SqlAlchemySearchRepository,
)
from app.adapters.identity_providers.firebase_phone import FirebasePhoneVerifier
from app.adapters.identity_providers.internal_jwt import InternalJWTProvider, verify_access_token
from app.adapters.parsing.resume_text_extractor import PdfDocxTextExtractor
from app.adapters.quotes.zen_quotes_provider import ZenQuotesProvider
from app.adapters.storage.s3_object_storage import S3ObjectStorageRepository
from app.ai_platform.llm_service.provider_interface import LLMProviderInterface
from app.ai_platform.llm_service.service import LLMService
from app.application.ai_platform.model_preference_service import ModelPreferenceService
from app.application.career_intelligence.catalog_query_service import CatalogQueryService
from app.application.career_intelligence.content_revision_service import ContentRevisionService
from app.application.career_intelligence.embedding_service import EmbeddingIndexingService
from app.application.career_intelligence.search_service import SearchService
from app.application.career_intelligence.skill_alias_admin_service import SkillAliasAdminService
from app.application.career_intelligence.skill_alias_resolution_service import (
    SkillAliasResolutionService,
)
from app.application.career_profile.career_goal_service import CareerGoalService
from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.career_profile_summary_service import (
    CareerProfileSummaryService,
)
from app.application.career_profile.clear_profile_service import ClearCareerProfileService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.application.career_profile.peer_endorsement_service import PeerEndorsementService
from app.application.career_profile.resume_export_service import ResumeExportService
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.chat.chat_service import ChatService
from app.application.identity.audit_service import AuditService
from app.application.identity.authenticate_user import AuthenticateUserService
from app.application.identity.delete_account import DeleteAccountService
from app.application.identity.get_current_user import GetCurrentUserService
from app.application.identity.list_audit_events import ListAuditEventsService
from app.application.identity.list_feature_flags import ListFeatureFlagsService
from app.application.identity.register_tenant import RegisterTenantService
from app.application.identity.request_organization_signup import (
    RequestOrganizationSignupService,
)
from app.application.identity.request_password_reset import RequestPasswordResetService
from app.application.identity.request_personal_signup import RequestPersonalSignupService
from app.application.identity.reset_password import ResetPasswordService
from app.application.identity.update_user_profile import UpdateUserProfileService
from app.application.identity.verify_signup import VerifySignupService
from app.application.platform_admin.grant_service import PlatformAdminService
from app.application.platform_admin.settings_service import PlatformSettingsService
from app.application.quotes.quote_of_the_day_service import QuoteOfTheDayService
from app.application.resume_intelligence.resume_extraction_service import ResumeExtractionService
from app.application.resume_intelligence.resume_merge_service import ResumeMergeService
from app.application.skill_intelligence.gap_analysis_service import GapAnalysisService
from app.application.system_status.system_status_service import SystemStatusService
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.identity_provider_interface import IdentityClaims
from app.core.logging import get_logger
from app.core.security import create_access_token, decode_access_token
from app.domain.identity.authorization import has_permission
from app.domain.identity.entities import Role

logger = get_logger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Plain session, no tenant context — for pre-auth flows
    (registration, login) that bind tenant context themselves once they
    know which tenant is in play.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_identity(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> IdentityClaims:
    """Resolve and verify the caller's identity from the Authorization
    header. Every protected route depends on this (directly or via
    require_permission) rather than decoding tokens itself.

    Also implements a sliding session: if the token is past the halfway
    point of its lifetime, a fresh one is minted and returned via the
    `X-Refreshed-Token` response header. The frontend's apiClient checks
    for this header on every response and silently swaps in the new
    token (see frontend/src/api/client.ts). This is deliberately not a
    separate refresh-token endpoint/flow (see
    docs/adr/ADR-003-authentication-strategy.md) — it reuses the
    already-verified access token's own claims, so a session only
    extends as a side effect of the user actually doing something, and
    a truly idle session still expires exactly as before. A user
    actively adding/editing data (hitting the API repeatedly) never
    reaches the original fixed expiry; someone who walks away does.
    """
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.", code="MISSING_TOKEN")

    identity = verify_access_token(credentials.credentials)
    _refresh_token_if_stale(credentials.credentials, identity, response)
    return identity


def _refresh_token_if_stale(token: str, identity: IdentityClaims, response: Response) -> None:
    settings = get_settings()
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001 -- already verified above; defensive no-op only
        return

    issued_at = payload.get("iat")
    if issued_at is None:
        return

    age_seconds = time.time() - issued_at
    half_life_seconds = (settings.jwt_access_token_expire_minutes * 60) / 2
    if age_seconds < half_life_seconds:
        return

    refreshed_token = create_access_token(
        subject=identity.user_id,
        extra_claims={
            "tenant_id": identity.tenant_id,
            "email": identity.email,
            "full_name": identity.full_name,
            "first_name": identity.first_name,
            "last_name": identity.last_name,
            "salutation": identity.salutation,
            "last_login_at": identity.last_login_at,
            "roles": list(identity.roles),
        },
    )
    response.headers["X-Refreshed-Token"] = refreshed_token


async def get_tenant_scoped_session(
    identity: IdentityClaims = Depends(get_current_identity),
) -> AsyncGenerator[AsyncSession, None]:
    """A session with RLS tenant context already bound from the caller's
    verified JWT. Every protected route that touches tenant-owned data
    should depend on this instead of get_db_session.
    """
    async with async_session_factory() as session:
        try:
            await set_tenant_context(session, UUID(identity.tenant_id))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_role_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyRoleRepository:
    return SqlAlchemyRoleRepository(session)


async def get_current_user_roles(
    identity: IdentityClaims = Depends(get_current_identity),
    roles: SqlAlchemyRoleRepository = Depends(get_role_repository),
) -> list[Role]:
    return await roles.list_for_user(UUID(identity.tenant_id), UUID(identity.user_id))


def require_permission(permission_code: str) -> Callable[..., Awaitable[IdentityClaims]]:
    """Dependency factory: returns a FastAPI dependency that raises
    ForbiddenError unless the current user holds `permission_code` via
    at least one of their assigned roles.

    Usage: `Depends(require_permission("audit_event:read"))` in a route
    signature. Enforced at the API layer (this module) but the actual
    has_permission check is pure domain logic
    (app/domain/identity/authorization.py) — this function's only job is
    wiring the current user's roles into that check and raising the
    right HTTP-mappable exception if it fails.
    """

    async def dependency(
        identity: IdentityClaims = Depends(get_current_identity),
        roles: list[Role] = Depends(get_current_user_roles),
    ) -> IdentityClaims:
        if not has_permission(roles, permission_code):
            raise ForbiddenError(
                f"Missing required permission: {permission_code}", code="PERMISSION_DENIED"
            )
        return identity

    return dependency


def get_platform_admin_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPlatformAdminRepository:
    """Plain session, no tenant context — platform_admins carries no RLS
    (see its own module docstring), so there's no tenant to scope to.
    """
    return SqlAlchemyPlatformAdminRepository(session)


def require_platform_permission(
    *permission_codes: str,
) -> Callable[..., Awaitable[IdentityClaims]]:
    """Dependency factory: the cross-tenant equivalent of
    require_permission. Checks the caller's own platform_admins grant
    directly by (tenant_id, user_id) from their JWT — no RLS-scoped role
    resolution involved, since this table has no RLS at all.

    Accepts one or more codes with OR semantics (any one is enough) —
    e.g. GET /platform-admin/settings accepts either
    platform.settings.view or platform.settings.edit, since someone
    granted edit-only access with no view grant would otherwise see
    "You don't have access to this page" despite genuinely being able
    to edit it once there — a real gap caught live granting exactly
    that combination. The single-code call sites (PATCH .../settings,
    the /admins.* routes) are unaffected; a single string is just the
    degenerate case of "any of one code."
    """

    async def dependency(
        identity: IdentityClaims = Depends(get_current_identity),
        grants: SqlAlchemyPlatformAdminRepository = Depends(get_platform_admin_repository),
    ) -> IdentityClaims:
        grant = await grants.get_for_user(UUID(identity.tenant_id), UUID(identity.user_id))
        if grant is None or not any(code in grant.permission_codes for code in permission_codes):
            raise ForbiddenError(
                f"Missing required platform permission: {' or '.join(permission_codes)}",
                code="PLATFORM_PERMISSION_DENIED",
            )
        return identity

    return dependency


def get_audit_service(session: AsyncSession = Depends(get_tenant_scoped_session)) -> AuditService:
    return AuditService(SqlAlchemyAuditEventRepository(session))


def get_request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- Pre-auth flow wiring (tenant registration, login) ---
# These use the plain (non-tenant-scoped) session because the tenant
# either doesn't exist yet (registration) or isn't known until the
# request body is parsed (login) — the services themselves call
# TenantContextBinder.bind() once they know which tenant is in play.
# See app/application/identity/register_tenant.py and authenticate_user.py.


def get_tenant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyTenantRepository:
    return SqlAlchemyTenantRepository(session)


def get_organization_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyOrganizationRepository:
    return SqlAlchemyOrganizationRepository(session)


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


def get_role_repository_plain(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyRoleRepository:
    return SqlAlchemyRoleRepository(session)


def get_personal_phone_login_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPersonalPhoneLoginRepository:
    """Plain (unscoped) session — used for phone login's pre-auth,
    cross-tenant lookup, before any tenant context exists. See
    get_personal_phone_login_repository_scoped for the tenant-scoped
    variant Settings > Profile writes through instead. Defined here
    (ahead of get_authenticate_user_service) rather than alongside its
    sibling get_pending_signup_repository further down — Depends()
    default args are evaluated at function-definition time, top to
    bottom, so a forward reference to a not-yet-defined function raises
    NameError at import time (hit this exact class of bug once already
    in this file, see get_email_provider/get_object_storage's own
    placement history)."""
    return SqlAlchemyPersonalPhoneLoginRepository(session)


def get_tenant_context_binder(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyTenantContextBinder:
    return SqlAlchemyTenantContextBinder(session)


def get_plain_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    return AuditService(SqlAlchemyAuditEventRepository(session))


def get_internal_jwt_provider(
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    roles: SqlAlchemyRoleRepository = Depends(get_role_repository_plain),
) -> InternalJWTProvider:
    return InternalJWTProvider(users=users, roles=roles)


def get_register_tenant_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    organizations: SqlAlchemyOrganizationRepository = Depends(get_organization_repository),
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    roles: SqlAlchemyRoleRepository = Depends(get_role_repository_plain),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
    audit: AuditService = Depends(get_plain_audit_service),
) -> RegisterTenantService:
    return RegisterTenantService(
        tenants=tenants,
        organizations=organizations,
        users=users,
        roles=roles,
        tenant_context=tenant_context,
        audit=audit,
    )


# Process-wide (lru_cache), not per-request — same rationale as
# get_anthropic_provider below. Returns None rather than raising when
# Firebase isn't configured yet (FIREBASE_PROJECT_ID/
# FIREBASE_SERVICE_ACCOUNT_FILE unset, or the key file isn't there yet)
# so that email/password login — which shares get_authenticate_user_service
# below — is never broken by an incomplete or absent phone-login setup;
# AuthenticateUserService.execute_phone turns a None verifier into a
# clean "not configured" error instead.
@lru_cache
def get_firebase_phone_verifier() -> FirebasePhoneVerifier | None:
    settings = get_settings()
    if not settings.firebase_project_id or not settings.firebase_service_account_file:
        return None
    try:
        return FirebasePhoneVerifier(
            project_id=settings.firebase_project_id,
            service_account_file=settings.firebase_service_account_file,
        )
    except Exception:
        logger.warning(
            "firebase_phone_verifier_init_failed",
            project_id=settings.firebase_project_id,
            service_account_file=settings.firebase_service_account_file,
        )
        return None


def get_authenticate_user_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
    identity_provider: InternalJWTProvider = Depends(get_internal_jwt_provider),
    audit: AuditService = Depends(get_plain_audit_service),
    phone_verifier: FirebasePhoneVerifier | None = Depends(get_firebase_phone_verifier),
    personal_phone_logins: SqlAlchemyPersonalPhoneLoginRepository = Depends(
        get_personal_phone_login_repository
    ),
) -> AuthenticateUserService:
    return AuthenticateUserService(
        tenants=tenants,
        tenant_context=tenant_context,
        identity_provider=identity_provider,
        audit=audit,
        phone_verifier=phone_verifier,
        personal_phone_logins=personal_phone_logins,
    )


def get_password_reset_token_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPasswordResetTokenRepository:
    return SqlAlchemyPasswordResetTokenRepository(session)


# Process-wide (lru_cache), not per-request — same rationale as
# get_anthropic_provider/get_quote_provider (a plain httpx-based
# adapter, no reason to reconstruct it every request).
@lru_cache
def get_email_provider() -> ResendEmailProvider:
    return ResendEmailProvider(get_settings())


async def get_resend_from_email(session: AsyncSession = Depends(get_db_session)) -> str:
    """The default sender address, resolved from platform_settings (the
    admin-editable "resend_from_email" key) at request time, falling
    back to the static RESEND_FROM_EMAIL env value if no admin has ever
    edited it. A plain session, not get_platform_settings_repository —
    that dependency is defined later in this file (see the "Platform
    admin wiring" section below) and Depends() default arguments are
    resolved at function-definition time, so referencing it here would
    raise NameError at import time.
    """
    setting = await SqlAlchemyPlatformSettingsRepository(session).get("resend_from_email")
    return setting.value if setting else get_settings().resend_from_email


async def get_resend_welcome_from_email(session: AsyncSession = Depends(get_db_session)) -> str:
    """Same as get_resend_from_email, for the "resend_welcome_from_email" key."""
    setting = await SqlAlchemyPlatformSettingsRepository(session).get("resend_welcome_from_email")
    return setting.value if setting else get_settings().resend_welcome_from_email


def get_request_password_reset_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    reset_tokens: SqlAlchemyPasswordResetTokenRepository = Depends(
        get_password_reset_token_repository
    ),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
    email_provider: ResendEmailProvider = Depends(get_email_provider),
    audit: AuditService = Depends(get_plain_audit_service),
    from_email: str = Depends(get_resend_from_email),
) -> RequestPasswordResetService:
    return RequestPasswordResetService(
        tenants=tenants,
        users=users,
        reset_tokens=reset_tokens,
        tenant_context=tenant_context,
        email_provider=email_provider,
        audit=audit,
        frontend_base_url=get_settings().frontend_base_url,
        from_email=from_email,
    )


def get_reset_password_service(
    reset_tokens: SqlAlchemyPasswordResetTokenRepository = Depends(
        get_password_reset_token_repository
    ),
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
    audit: AuditService = Depends(get_plain_audit_service),
) -> ResetPasswordService:
    return ResetPasswordService(
        reset_tokens=reset_tokens,
        users=users,
        tenant_context=tenant_context,
        audit=audit,
    )


def get_pending_signup_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPendingSignupRepository:
    return SqlAlchemyPendingSignupRepository(session)


def get_request_personal_signup_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    pending_signups: SqlAlchemyPendingSignupRepository = Depends(get_pending_signup_repository),
    email_provider: ResendEmailProvider = Depends(get_email_provider),
    from_email: str = Depends(get_resend_from_email),
) -> RequestPersonalSignupService:
    return RequestPersonalSignupService(
        tenants=tenants,
        pending_signups=pending_signups,
        email_provider=email_provider,
        frontend_base_url=get_settings().frontend_base_url,
        from_email=from_email,
    )


def get_request_organization_signup_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    pending_signups: SqlAlchemyPendingSignupRepository = Depends(get_pending_signup_repository),
    email_provider: ResendEmailProvider = Depends(get_email_provider),
    from_email: str = Depends(get_resend_from_email),
) -> RequestOrganizationSignupService:
    return RequestOrganizationSignupService(
        tenants=tenants,
        pending_signups=pending_signups,
        email_provider=email_provider,
        frontend_base_url=get_settings().frontend_base_url,
        from_email=from_email,
    )


def get_verify_signup_service(
    pending_signups: SqlAlchemyPendingSignupRepository = Depends(get_pending_signup_repository),
    register_tenant: RegisterTenantService = Depends(get_register_tenant_service),
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    identity_provider: InternalJWTProvider = Depends(get_internal_jwt_provider),
    email_provider: ResendEmailProvider = Depends(get_email_provider),
    welcome_from_email: str = Depends(get_resend_welcome_from_email),
) -> VerifySignupService:
    return VerifySignupService(
        pending_signups=pending_signups,
        register_tenant=register_tenant,
        users=users,
        identity_provider=identity_provider,
        email_provider=email_provider,
        welcome_from_email=welcome_from_email,
    )


# --- Platform admin wiring (protected, but genuinely cross-tenant) ---
# Every repository here uses get_db_session (no tenant context) since
# platform_admins/platform_settings carry no RLS at all — see
# app/domain/platform_admin/entities.py's module docstring.


def get_platform_settings_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPlatformSettingsRepository:
    return SqlAlchemyPlatformSettingsRepository(session)


def get_platform_admin_service(
    grants: SqlAlchemyPlatformAdminRepository = Depends(get_platform_admin_repository),
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    users: SqlAlchemyUserRepository = Depends(get_user_repository),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
) -> PlatformAdminService:
    return PlatformAdminService(
        grants=grants, tenants=tenants, users=users, tenant_context=tenant_context
    )


def get_platform_settings_service(
    settings_repo: SqlAlchemyPlatformSettingsRepository = Depends(
        get_platform_settings_repository
    ),
) -> PlatformSettingsService:
    return PlatformSettingsService(settings_repo)


# --- Post-auth flow wiring (protected routes) ---
# These use get_tenant_scoped_session, which binds RLS context from the
# caller's already-verified JWT (see get_tenant_scoped_session above).


def get_user_repository_scoped(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


def get_personal_phone_login_repository_scoped(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyPersonalPhoneLoginRepository:
    """Same underlying session as get_user_repository_scoped/
    get_role_repository within a request (FastAPI caches Depends() per
    callable per request) — required so UpdateUserProfileService's
    profile-field save and this table's upsert/delete commit or roll
    back together as one transaction, not two independent ones."""
    return SqlAlchemyPersonalPhoneLoginRepository(session)


def get_feature_flag_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyFeatureFlagRepository:
    return SqlAlchemyFeatureFlagRepository(session)


def get_current_user_service(
    users: SqlAlchemyUserRepository = Depends(get_user_repository_scoped),
    roles: SqlAlchemyRoleRepository = Depends(get_role_repository),
) -> GetCurrentUserService:
    return GetCurrentUserService(users=users, roles=roles)


def get_update_user_profile_service(
    users: SqlAlchemyUserRepository = Depends(get_user_repository_scoped),
    roles: SqlAlchemyRoleRepository = Depends(get_role_repository),
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    personal_phone_logins: SqlAlchemyPersonalPhoneLoginRepository = Depends(
        get_personal_phone_login_repository_scoped
    ),
) -> UpdateUserProfileService:
    return UpdateUserProfileService(
        users=users, roles=roles, tenants=tenants, personal_phone_logins=personal_phone_logins
    )


def get_account_deletion_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyAccountDeletionRepository:
    return SqlAlchemyAccountDeletionRepository(session)


def get_audit_event_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyAuditEventRepository:
    return SqlAlchemyAuditEventRepository(session)


def get_list_audit_events_service(
    audit_events: SqlAlchemyAuditEventRepository = Depends(get_audit_event_repository),
) -> ListAuditEventsService:
    return ListAuditEventsService(audit_events)


def get_list_feature_flags_service(
    feature_flags: SqlAlchemyFeatureFlagRepository = Depends(get_feature_flag_repository),
) -> ListFeatureFlagsService:
    return ListFeatureFlagsService(feature_flags)


# --- Career Profile domain wiring ---
# All career-profile data is self-service (a user manages their own
# profile/experience/education/certifications/goals), so these endpoints
# only require an authenticated identity — no additional RBAC permission
# — unlike the admin-facing audit-events/feature-flags endpoints above.


def get_career_profile_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyCareerProfileRepository:
    return SqlAlchemyCareerProfileRepository(session)


def get_career_profile_version_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyCareerProfileVersionRepository:
    return SqlAlchemyCareerProfileVersionRepository(session)


def get_experience_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyExperienceRepository:
    return SqlAlchemyExperienceRepository(session)


def get_education_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyEducationRepository:
    return SqlAlchemyEducationRepository(session)


def get_certification_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyCertificationRepository:
    return SqlAlchemyCertificationRepository(session)


def get_career_goal_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyCareerGoalRepository:
    return SqlAlchemyCareerGoalRepository(session)


def get_target_role_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyTargetRoleRepository:
    return SqlAlchemyTargetRoleRepository(session)


def get_object_storage() -> S3ObjectStorageRepository:
    return S3ObjectStorageRepository(get_settings())


def get_delete_account_service(
    account_deletion: SqlAlchemyAccountDeletionRepository = Depends(
        get_account_deletion_repository
    ),
    storage: S3ObjectStorageRepository = Depends(get_object_storage),
) -> DeleteAccountService:
    return DeleteAccountService(
        account_deletion=account_deletion, photo_storage=storage, resume_storage=storage
    )


def get_career_profile_service(
    profiles: SqlAlchemyCareerProfileRepository = Depends(get_career_profile_repository),
    versions: SqlAlchemyCareerProfileVersionRepository = Depends(
        get_career_profile_version_repository
    ),
    storage: S3ObjectStorageRepository = Depends(get_object_storage),
) -> CareerProfileService:
    return CareerProfileService(profiles, versions, storage)


def get_career_highlight_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyCareerHighlightRepository:
    return SqlAlchemyCareerHighlightRepository(session)


def get_key_achievement_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyKeyAchievementRepository:
    return SqlAlchemyKeyAchievementRepository(session)


def get_peer_endorsement_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyPeerEndorsementRepository:
    return SqlAlchemyPeerEndorsementRepository(session)


def get_resume_export_service(
    profiles: SqlAlchemyCareerProfileRepository = Depends(get_career_profile_repository),
    experiences: SqlAlchemyExperienceRepository = Depends(get_experience_repository),
    educations: SqlAlchemyEducationRepository = Depends(get_education_repository),
    certifications: SqlAlchemyCertificationRepository = Depends(get_certification_repository),
    career_highlights: SqlAlchemyCareerHighlightRepository = Depends(
        get_career_highlight_repository
    ),
    key_achievements: SqlAlchemyKeyAchievementRepository = Depends(get_key_achievement_repository),
    career_goals: SqlAlchemyCareerGoalRepository = Depends(get_career_goal_repository),
    peer_endorsements: SqlAlchemyPeerEndorsementRepository = Depends(
        get_peer_endorsement_repository
    ),
    target_roles: SqlAlchemyTargetRoleRepository = Depends(get_target_role_repository),
    users: SqlAlchemyUserRepository = Depends(get_user_repository_scoped),
    storage: S3ObjectStorageRepository = Depends(get_object_storage),
) -> ResumeExportService:
    return ResumeExportService(
        profiles=profiles,
        experiences=experiences,
        educations=educations,
        certifications=certifications,
        career_highlights=career_highlights,
        key_achievements=key_achievements,
        career_goals=career_goals,
        peer_endorsements=peer_endorsements,
        target_roles=target_roles,
        users=users,
        storage=storage,
    )


def get_career_highlight_service(
    highlights: SqlAlchemyCareerHighlightRepository = Depends(get_career_highlight_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> CareerHighlightService:
    return CareerHighlightService(highlights, career_profiles)


def get_key_achievement_service(
    achievements: SqlAlchemyKeyAchievementRepository = Depends(get_key_achievement_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> KeyAchievementService:
    return KeyAchievementService(achievements, career_profiles)


def get_peer_endorsement_service(
    endorsements: SqlAlchemyPeerEndorsementRepository = Depends(get_peer_endorsement_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> PeerEndorsementService:
    return PeerEndorsementService(endorsements, career_profiles)


def get_experience_service(
    experiences: SqlAlchemyExperienceRepository = Depends(get_experience_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> ExperienceService:
    return ExperienceService(experiences, career_profiles)


def get_education_service(
    educations: SqlAlchemyEducationRepository = Depends(get_education_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> EducationService:
    return EducationService(educations, career_profiles)


def get_certification_service(
    certifications: SqlAlchemyCertificationRepository = Depends(get_certification_repository),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> CertificationService:
    return CertificationService(certifications, career_profiles)


def get_career_goal_service(
    goals: SqlAlchemyCareerGoalRepository = Depends(get_career_goal_repository),
) -> CareerGoalService:
    return CareerGoalService(goals)


def get_clear_career_profile_service(
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
    experiences: ExperienceService = Depends(get_experience_service),
    educations: EducationService = Depends(get_education_service),
    certifications: CertificationService = Depends(get_certification_service),
    career_highlights: CareerHighlightService = Depends(get_career_highlight_service),
    key_achievements: KeyAchievementService = Depends(get_key_achievement_service),
    peer_endorsements: PeerEndorsementService = Depends(get_peer_endorsement_service),
    career_goals: CareerGoalService = Depends(get_career_goal_service),
) -> ClearCareerProfileService:
    return ClearCareerProfileService(
        career_profiles,
        experiences,
        educations,
        certifications,
        career_highlights,
        key_achievements,
        peer_endorsements,
        career_goals,
    )


def get_career_profile_summary_service(
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
    experiences: ExperienceService = Depends(get_experience_service),
    educations: EducationService = Depends(get_education_service),
    certifications: CertificationService = Depends(get_certification_service),
    career_highlights: CareerHighlightService = Depends(get_career_highlight_service),
    key_achievements: KeyAchievementService = Depends(get_key_achievement_service),
) -> CareerProfileSummaryService:
    return CareerProfileSummaryService(
        career_profiles,
        experiences,
        educations,
        certifications,
        career_highlights,
        key_achievements,
    )


def get_target_role_service(
    target_roles: SqlAlchemyTargetRoleRepository = Depends(get_target_role_repository),
) -> TargetRoleService:
    return TargetRoleService(target_roles)


# --- AI Platform wiring (Phase 4) ---
# get_anthropic_provider / get_ollama_provider are process-wide
# (lru_cache), not per-request — same rationale as get_quote_provider
# below (the Anthropic one wraps an AsyncAnthropic client that manages
# its own httpx connection pool; the Ollama one is stateless but there's
# no reason to reconstruct it every request either). The prompt/model
# registries and invocation logger are per-request since they need the
# request's (possibly tenant-scoped) DB session.


@lru_cache
def get_anthropic_provider() -> AnthropicProvider:
    return AnthropicProvider(get_settings())


@lru_cache
def get_ollama_provider() -> OllamaProvider:
    return OllamaProvider(get_settings())


@lru_cache
def get_groq_provider() -> GroqProvider:
    return GroqProvider(get_settings())


@lru_cache
def get_ollama_embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(get_settings())


def get_prompt_registry(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyPromptRegistry:
    return SqlAlchemyPromptRegistry(session)


def get_model_registry(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyModelRegistry:
    return SqlAlchemyModelRegistry(session)


def get_invocation_logger(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyInvocationLogger:
    return SqlAlchemyInvocationLogger(session)


def get_llm_service(
    anthropic_provider: AnthropicProvider = Depends(get_anthropic_provider),
    ollama_provider: OllamaProvider = Depends(get_ollama_provider),
    groq_provider: GroqProvider = Depends(get_groq_provider),
    prompts: SqlAlchemyPromptRegistry = Depends(get_prompt_registry),
    models: SqlAlchemyModelRegistry = Depends(get_model_registry),
    invocations: SqlAlchemyInvocationLogger = Depends(get_invocation_logger),
) -> LLMService:
    # Keyed by ModelVersion.provider — a third provider is one more
    # entry here plus its own adapter, not a change to LLMService.
    providers: dict[str, LLMProviderInterface] = {
        "anthropic": anthropic_provider,
        "ollama": ollama_provider,
        "groq": groq_provider,
    }
    return LLMService(providers=providers, prompts=prompts, models=models, invocations=invocations)


def get_model_preference_service(
    models: SqlAlchemyModelRegistry = Depends(get_model_registry),
    users: SqlAlchemyUserRepository = Depends(get_user_repository_scoped),
) -> ModelPreferenceService:
    return ModelPreferenceService(models, users)


# --- Chat domain wiring (UI enhancement brief Part 1.2) ---
# Self-service, same as Career Profile above — a user only ever sends
# messages into / continues their own conversations.


def get_chat_conversation_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyChatConversationRepository:
    return SqlAlchemyChatConversationRepository(session)


def get_chat_message_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyChatMessageRepository:
    return SqlAlchemyChatMessageRepository(session)


def get_chat_service(
    conversations: SqlAlchemyChatConversationRepository = Depends(
        get_chat_conversation_repository
    ),
    messages: SqlAlchemyChatMessageRepository = Depends(get_chat_message_repository),
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatService:
    return ChatService(conversations, messages, llm_service)


# --- Resume Intelligence domain wiring (Phase 5) ---
# Self-service, same as Career Profile above. get_resume_text_extractor
# is process-wide (lru_cache) — PdfDocxTextExtractor is stateless, no
# reason to reconstruct it every request.


def get_resume_repository(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyResumeRepository:
    return SqlAlchemyResumeRepository(session)


@lru_cache
def get_resume_text_extractor() -> PdfDocxTextExtractor:
    return PdfDocxTextExtractor()


def get_resume_extraction_service(
    resumes: SqlAlchemyResumeRepository = Depends(get_resume_repository),
    storage: S3ObjectStorageRepository = Depends(get_object_storage),
    extractor: PdfDocxTextExtractor = Depends(get_resume_text_extractor),
    llm_service: LLMService = Depends(get_llm_service),
) -> ResumeExtractionService:
    return ResumeExtractionService(resumes, storage, extractor, llm_service)


def get_resume_merge_service(
    resumes: SqlAlchemyResumeRepository = Depends(get_resume_repository),
    experiences: ExperienceService = Depends(get_experience_service),
    educations: EducationService = Depends(get_education_service),
    certifications: CertificationService = Depends(get_certification_service),
    career_highlights: CareerHighlightService = Depends(get_career_highlight_service),
    key_achievements: KeyAchievementService = Depends(get_key_achievement_service),
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
) -> ResumeMergeService:
    return ResumeMergeService(
        resumes,
        experiences,
        educations,
        certifications,
        career_highlights,
        key_achievements,
        career_profiles,
    )


# --- Quote of the day wiring (UI enhancement brief Part 1.3) ---
# get_quote_provider is process-wide (lru_cache), not per-request — the
# provider's in-memory daily cache (see ZenQuotesProvider) would reset on
# every request otherwise, defeating the point of caching it at all.


@lru_cache
def get_quote_provider() -> ZenQuotesProvider:
    return ZenQuotesProvider(get_settings())


def get_quote_of_the_day_service(
    provider: ZenQuotesProvider = Depends(get_quote_provider),
) -> QuoteOfTheDayService:
    return QuoteOfTheDayService(provider)


# --- Dashboard System Status wiring ---
# Status-only (no restart execution) — see SystemStatusService's own
# docstring for why. A fresh instance per request is fine, unlike the
# quote provider above: there's no in-process cache to preserve, every
# call performs live checks.


def get_system_status_service() -> SystemStatusService:
    return SystemStatusService(get_settings())


# --- Skill Intelligence domain wiring (Phase 3, simplified per ADR-005) ---
# The catalog/proficiency/category model (Skill, SkillCategory, UserSkill,
# RoleTag, TargetRoleSkill) was removed entirely — Gap Analysis is now pure
# computation over career_profile's two existing services (My Skills reads
# straight off CareerProfileService via the career-profile router; Target
# Role Skill Requirements reads/writes straight off TargetRoleService).


def get_gap_analysis_service(
    career_profiles: CareerProfileService = Depends(get_career_profile_service),
    target_roles: TargetRoleService = Depends(get_target_role_service),
) -> GapAnalysisService:
    return GapAnalysisService(career_profiles, target_roles)


# --- Career Intelligence Knowledge Graph wiring (Phase 4.5.1 / MVP 1) ---
# All CIKG tables are global reference data (no tenant_id, no RLS — see
# app/adapters/db/models/career_intelligence.py), so these use the plain
# get_db_session, not get_tenant_scoped_session.


def get_skill_category_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySkillCategoryRepository:
    return SqlAlchemySkillCategoryRepository(session)


def get_competency_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyCompetencyRepository:
    return SqlAlchemyCompetencyRepository(session)


def get_skill_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySkillRepository:
    return SqlAlchemySkillRepository(session)


def get_cikg_role_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyCikgRoleRepository:
    return SqlAlchemyCikgRoleRepository(session)


def get_category_parent_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyCategoryParentRepository:
    return SqlAlchemyCategoryParentRepository(session)


def get_skill_category_membership_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySkillCategoryMembershipRepository:
    return SqlAlchemySkillCategoryMembershipRepository(session)


def get_skill_competency_membership_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySkillCompetencyMembershipRepository:
    return SqlAlchemySkillCompetencyMembershipRepository(session)


def get_related_skill_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyRelatedSkillRepository:
    return SqlAlchemyRelatedSkillRepository(session)


def get_role_required_skill_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyRoleRequiredSkillRepository:
    return SqlAlchemyRoleRequiredSkillRepository(session)


def get_skill_alias_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySkillAliasRepository:
    return SqlAlchemySkillAliasRepository(session)


def get_skill_alias_admin_service(
    aliases: SqlAlchemySkillAliasRepository = Depends(get_skill_alias_repository),
) -> SkillAliasAdminService:
    return SkillAliasAdminService(aliases)


def get_prerequisite_of_edge_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyPrerequisiteOfEdgeRepository:
    return SqlAlchemyPrerequisiteOfEdgeRepository(session)


def get_specializes_edge_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySpecializesEdgeRepository:
    return SqlAlchemySpecializesEdgeRepository(session)


def get_synonym_of_edge_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySynonymOfEdgeRepository:
    return SqlAlchemySynonymOfEdgeRepository(session)


def get_content_revision_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyContentRevisionRepository:
    return SqlAlchemyContentRevisionRepository(session)


def get_content_history_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyContentHistoryRepository:
    return SqlAlchemyContentHistoryRepository(session)


def get_content_revision_service(
    categories: SqlAlchemySkillCategoryRepository = Depends(get_skill_category_repository),
    competencies: SqlAlchemyCompetencyRepository = Depends(get_competency_repository),
    skills: SqlAlchemySkillRepository = Depends(get_skill_repository),
    roles: SqlAlchemyCikgRoleRepository = Depends(get_cikg_role_repository),
    category_parents: SqlAlchemyCategoryParentRepository = Depends(
        get_category_parent_repository
    ),
    skill_category_memberships: SqlAlchemySkillCategoryMembershipRepository = Depends(
        get_skill_category_membership_repository
    ),
    skill_competency_memberships: SqlAlchemySkillCompetencyMembershipRepository = Depends(
        get_skill_competency_membership_repository
    ),
    related_skills: SqlAlchemyRelatedSkillRepository = Depends(get_related_skill_repository),
    role_required_skills: SqlAlchemyRoleRequiredSkillRepository = Depends(
        get_role_required_skill_repository
    ),
    prerequisite_of_edges: SqlAlchemyPrerequisiteOfEdgeRepository = Depends(
        get_prerequisite_of_edge_repository
    ),
    specializes_edges: SqlAlchemySpecializesEdgeRepository = Depends(
        get_specializes_edge_repository
    ),
    synonym_of_edges: SqlAlchemySynonymOfEdgeRepository = Depends(get_synonym_of_edge_repository),
    revisions: SqlAlchemyContentRevisionRepository = Depends(get_content_revision_repository),
    history: SqlAlchemyContentHistoryRepository = Depends(get_content_history_repository),
) -> ContentRevisionService:
    return ContentRevisionService(
        categories=categories,
        competencies=competencies,
        skills=skills,
        roles=roles,
        category_parents=category_parents,
        skill_category_memberships=skill_category_memberships,
        skill_competency_memberships=skill_competency_memberships,
        related_skills=related_skills,
        role_required_skills=role_required_skills,
        prerequisite_of_edges=prerequisite_of_edges,
        specializes_edges=specializes_edges,
        synonym_of_edges=synonym_of_edges,
        revisions=revisions,
        history=history,
    )


def get_catalog_query_service(
    categories: SqlAlchemySkillCategoryRepository = Depends(get_skill_category_repository),
    competencies: SqlAlchemyCompetencyRepository = Depends(get_competency_repository),
    skills: SqlAlchemySkillRepository = Depends(get_skill_repository),
    roles: SqlAlchemyCikgRoleRepository = Depends(get_cikg_role_repository),
    category_parents: SqlAlchemyCategoryParentRepository = Depends(
        get_category_parent_repository
    ),
    skill_category_memberships: SqlAlchemySkillCategoryMembershipRepository = Depends(
        get_skill_category_membership_repository
    ),
    related_skills: SqlAlchemyRelatedSkillRepository = Depends(get_related_skill_repository),
    role_required_skills: SqlAlchemyRoleRequiredSkillRepository = Depends(
        get_role_required_skill_repository
    ),
    aliases: SqlAlchemySkillAliasRepository = Depends(get_skill_alias_repository),
) -> CatalogQueryService:
    return CatalogQueryService(
        categories=categories,
        competencies=competencies,
        skills=skills,
        roles=roles,
        category_parents=category_parents,
        skill_category_memberships=skill_category_memberships,
        related_skills=related_skills,
        role_required_skills=role_required_skills,
        aliases=aliases,
    )


def get_skill_alias_resolution_service(
    aliases: SqlAlchemySkillAliasRepository = Depends(get_skill_alias_repository),
    skills: SqlAlchemySkillRepository = Depends(get_skill_repository),
) -> SkillAliasResolutionService:
    return SkillAliasResolutionService(aliases, skills)


# --- CIKG search wiring (Phase 4.5.1 MVP 2A) ---
# embedding_models/content_embeddings are global reference data like
# every other CIKG table (get_db_session, not tenant-scoped).


def get_embedding_model_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyEmbeddingModelRepository:
    return SqlAlchemyEmbeddingModelRepository(session)


def get_content_embedding_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyContentEmbeddingRepository:
    return SqlAlchemyContentEmbeddingRepository(session)


def get_search_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySearchRepository:
    return SqlAlchemySearchRepository(session)


def get_embedding_indexing_service(
    embedding_provider: OllamaEmbeddingProvider = Depends(get_ollama_embedding_provider),
    embedding_models: SqlAlchemyEmbeddingModelRepository = Depends(get_embedding_model_repository),
    content_embeddings: SqlAlchemyContentEmbeddingRepository = Depends(
        get_content_embedding_repository
    ),
    skills: SqlAlchemySkillRepository = Depends(get_skill_repository),
    roles: SqlAlchemyCikgRoleRepository = Depends(get_cikg_role_repository),
    competencies: SqlAlchemyCompetencyRepository = Depends(get_competency_repository),
) -> EmbeddingIndexingService:
    settings = get_settings()
    return EmbeddingIndexingService(
        embedding_provider,
        embedding_models,
        content_embeddings,
        skills,
        roles,
        competencies,
        model_name=settings.cikg_embedding_model,
        provider_name="ollama",
        dimensions=settings.cikg_embedding_dimensions,
    )


def get_search_service(
    search_repo: SqlAlchemySearchRepository = Depends(get_search_repository),
    related_skills: SqlAlchemyRelatedSkillRepository = Depends(get_related_skill_repository),
    embedding_models: SqlAlchemyEmbeddingModelRepository = Depends(get_embedding_model_repository),
    embedding_provider: OllamaEmbeddingProvider = Depends(get_ollama_embedding_provider),
    alias_resolver: SkillAliasResolutionService = Depends(get_skill_alias_resolution_service),
) -> SearchService:
    return SearchService(
        search_repo, related_skills, embedding_models, embedding_provider, alias_resolver
    )
