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
    SqlAlchemyPeerEndorsementRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyTargetRoleRepository,
    SqlAlchemyTenantContextBinder,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.adapters.db.repositories.career_profile import SqlAlchemyCareerProfileVersionRepository
from app.adapters.db.repositories.chat import (
    SqlAlchemyChatConversationRepository,
    SqlAlchemyChatMessageRepository,
)
from app.adapters.identity_providers.internal_jwt import InternalJWTProvider, verify_access_token
from app.adapters.quotes.zen_quotes_provider import ZenQuotesProvider
from app.adapters.storage.s3_object_storage import S3ObjectStorageRepository
from app.application.career_profile.career_goal_service import CareerGoalService
from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.application.career_profile.peer_endorsement_service import PeerEndorsementService
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.chat.chat_service import ChatService
from app.application.identity.audit_service import AuditService
from app.application.identity.authenticate_user import AuthenticateUserService
from app.application.identity.get_current_user import GetCurrentUserService
from app.application.identity.list_audit_events import ListAuditEventsService
from app.application.identity.list_feature_flags import ListFeatureFlagsService
from app.application.identity.register_tenant import RegisterTenantService
from app.application.identity.update_user_profile import UpdateUserProfileService
from app.application.quotes.quote_of_the_day_service import QuoteOfTheDayService
from app.application.skill_intelligence.gap_analysis_service import GapAnalysisService
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.identity_provider_interface import IdentityClaims
from app.core.security import create_access_token, decode_access_token
from app.domain.identity.authorization import has_permission
from app.domain.identity.entities import Role

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


def get_authenticate_user_service(
    tenants: SqlAlchemyTenantRepository = Depends(get_tenant_repository),
    tenant_context: SqlAlchemyTenantContextBinder = Depends(get_tenant_context_binder),
    identity_provider: InternalJWTProvider = Depends(get_internal_jwt_provider),
    audit: AuditService = Depends(get_plain_audit_service),
) -> AuthenticateUserService:
    return AuthenticateUserService(
        tenants=tenants,
        tenant_context=tenant_context,
        identity_provider=identity_provider,
        audit=audit,
    )


# --- Post-auth flow wiring (protected routes) ---
# These use get_tenant_scoped_session, which binds RLS context from the
# caller's already-verified JWT (see get_tenant_scoped_session above).


def get_user_repository_scoped(
    session: AsyncSession = Depends(get_tenant_scoped_session),
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


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
) -> UpdateUserProfileService:
    return UpdateUserProfileService(users=users, roles=roles)


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


def get_target_role_service(
    target_roles: SqlAlchemyTargetRoleRepository = Depends(get_target_role_repository),
) -> TargetRoleService:
    return TargetRoleService(target_roles)


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
) -> ChatService:
    return ChatService(conversations, messages)


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
