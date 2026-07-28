"""Identity API routes.

Thin per section 3 of backend-architecture.md: parse input (Pydantic
already did that), call one application service, map the result to a
response schema. No business logic lives here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_authenticate_user_service,
    get_current_identity,
    get_current_user_service,
    get_list_audit_events_service,
    get_list_feature_flags_service,
    get_register_tenant_service,
    get_update_user_profile_service,
    require_permission,
)
from app.api.v1.identity.schemas import (
    AuditEventResponse,
    CurrentUserResponse,
    FeatureFlagResponse,
    LoginRequest,
    LoginResponse,
    RegisterTenantRequest,
    RegisterTenantResponse,
    UpdateCurrentUserRequest,
)
from app.application.identity.authenticate_user import AuthenticateUserService
from app.application.identity.get_current_user import GetCurrentUserService
from app.application.identity.list_audit_events import ListAuditEventsService
from app.application.identity.list_feature_flags import ListFeatureFlagsService
from app.application.identity.register_tenant import RegisterTenantService
from app.application.identity.update_user_profile import UpdateUserProfileService
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(prefix="/identity", tags=["identity"])


@router.post("/tenants", response_model=RegisterTenantResponse, status_code=201)
async def register_tenant(
    request: RegisterTenantRequest,
    service: RegisterTenantService = Depends(get_register_tenant_service),
) -> RegisterTenantResponse:
    result = await service.execute(
        tenant_name=request.tenant_name,
        subdomain=request.subdomain,
        organization_name=request.organization_name,
        admin_email=request.admin_email,
        admin_salutation=request.admin_salutation,
        admin_first_name=request.admin_first_name,
        admin_last_name=request.admin_last_name,
        admin_password=request.admin_password,
    )
    return RegisterTenantResponse(
        tenant_id=result.tenant_id,
        organization_id=result.organization_id,
        admin_user_id=result.admin_user_id,
        admin_email=result.admin_email,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    service: AuthenticateUserService = Depends(get_authenticate_user_service),
) -> LoginResponse:
    result = await service.execute(
        subdomain=request.subdomain, email=request.email, password=request.password
    )
    return LoginResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        tenant_id=result.tenant_id,
        email=result.email,
        full_name=result.full_name,
        first_name=result.first_name,
        last_name=result.last_name,
        salutation=result.salutation,
        last_login_at=result.last_login_at,
        roles=list(result.roles),
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    identity: IdentityClaims = Depends(get_current_identity),
    service: GetCurrentUserService = Depends(get_current_user_service),
) -> CurrentUserResponse:
    result = await service.execute(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return CurrentUserResponse(
        user_id=result.user_id,
        tenant_id=result.tenant_id,
        org_id=result.org_id,
        email=result.email,
        full_name=result.full_name,
        salutation=result.salutation,
        first_name=result.first_name,
        last_name=result.last_name,
        phone_number=result.phone_number,
        country=result.country,
        language=result.language,
        address_line1=result.address_line1,
        address_line2=result.address_line2,
        city=result.city,
        state=result.state,
        postal_code=result.postal_code,
        roles=list(result.roles),
    )


@router.patch("/me", response_model=CurrentUserResponse)
async def update_me(
    request: UpdateCurrentUserRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: UpdateUserProfileService = Depends(get_update_user_profile_service),
) -> CurrentUserResponse:
    result = await service.execute(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        salutation=request.salutation,
        first_name=request.first_name,
        last_name=request.last_name,
        phone_number=request.phone_number,
        country=request.country,
        language=request.language,
        address_line1=request.address_line1,
        address_line2=request.address_line2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
    )
    return CurrentUserResponse(
        user_id=result.user_id,
        tenant_id=result.tenant_id,
        org_id=result.org_id,
        email=result.email,
        full_name=result.full_name,
        salutation=result.salutation,
        first_name=result.first_name,
        last_name=result.last_name,
        phone_number=result.phone_number,
        country=result.country,
        language=result.language,
        address_line1=result.address_line1,
        address_line2=result.address_line2,
        city=result.city,
        state=result.state,
        postal_code=result.postal_code,
        roles=list(result.roles),
    )


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    identity: IdentityClaims = Depends(require_permission("audit_event:read")),
    service: ListAuditEventsService = Depends(get_list_audit_events_service),
) -> list[AuditEventResponse]:
    events = await service.execute(tenant_id=UUID(identity.tenant_id))
    return [
        AuditEventResponse(
            id=event.id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            occurred_at=event.occurred_at.isoformat(),
            metadata=event.metadata,
        )
        for event in events
    ]


@router.get("/feature-flags", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    identity: IdentityClaims = Depends(require_permission("feature_flag:read")),
    service: ListFeatureFlagsService = Depends(get_list_feature_flags_service),
) -> list[FeatureFlagResponse]:
    flags = await service.execute(tenant_id=UUID(identity.tenant_id))
    return [
        FeatureFlagResponse(
            id=flag.id,
            key=flag.key,
            enabled=flag.enabled,
            config=flag.config,
            is_global_default=flag.tenant_id is None,
        )
        for flag in flags
    ]
