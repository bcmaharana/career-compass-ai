"""Identity API routes.

Thin per section 3 of backend-architecture.md: parse input (Pydantic
already did that), call one application service, map the result to a
response schema. No business logic lives here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_authenticate_user_service,
    get_current_identity,
    get_current_user_service,
    get_delete_account_service,
    get_list_audit_events_service,
    get_list_feature_flags_service,
    get_platform_account_deletion_service,
    get_platform_handoff_service,
    get_register_tenant_service,
    get_request_organization_signup_service,
    get_request_password_reset_service,
    get_request_personal_signup_service,
    get_reset_password_service,
    get_update_user_profile_service,
    get_verify_signup_service,
    require_permission,
)
from app.api.v1.identity.schemas import (
    AuditEventResponse,
    CurrentUserResponse,
    FeatureFlagResponse,
    LoginRequest,
    LoginResponse,
    OrganizationSignupRequest,
    PersonalSignupRequest,
    PhoneLoginRequest,
    PlatformAccountDeletedRequest,
    PlatformHandoffRequest,
    RegisterTenantRequest,
    RegisterTenantResponse,
    RequestPasswordResetRequest,
    RequestPasswordResetResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupRequestResponse,
    UpdateCurrentUserRequest,
    VerifySignupRequest,
)
from app.application.identity.authenticate_user import AuthenticateUserService
from app.application.identity.delete_account import DeleteAccountService
from app.application.identity.dto import LoginResult
from app.application.identity.get_current_user import GetCurrentUserService
from app.application.identity.list_audit_events import ListAuditEventsService
from app.application.identity.list_feature_flags import ListFeatureFlagsService
from app.adapters.identity_providers.platform_deletion_verifier import (
    verify_platform_deletion_assertion,
)
from app.application.identity.platform_account_deletion import PlatformAccountDeletionService
from app.application.identity.platform_handoff import PlatformHandoffService
from app.application.identity.register_tenant import RegisterTenantService
from app.application.identity.request_organization_signup import (
    RequestOrganizationSignupService,
)
from app.application.identity.request_password_reset import RequestPasswordResetService
from app.application.identity.request_personal_signup import RequestPersonalSignupService
from app.application.identity.reset_password import ResetPasswordService
from app.application.identity.update_user_profile import UpdateUserProfileService
from app.application.identity.verify_signup import VerifySignupService
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


@router.post("/signup/personal", response_model=SignupRequestResponse, status_code=202)
async def signup_personal(
    request: PersonalSignupRequest,
    service: RequestPersonalSignupService = Depends(get_request_personal_signup_service),
) -> SignupRequestResponse:
    await service.execute(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name,
    )
    return SignupRequestResponse()


@router.post("/signup/organization", response_model=SignupRequestResponse, status_code=202)
async def signup_organization(
    request: OrganizationSignupRequest,
    service: RequestOrganizationSignupService = Depends(get_request_organization_signup_service),
) -> SignupRequestResponse:
    await service.execute(
        tenant_name=request.tenant_name,
        subdomain=request.subdomain,
        organization_name=request.organization_name,
        admin_email=request.admin_email,
        admin_password=request.admin_password,
        admin_first_name=request.admin_first_name,
        admin_last_name=request.admin_last_name,
    )
    return SignupRequestResponse()


def _login_response(result: LoginResult) -> LoginResponse:
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


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    service: AuthenticateUserService = Depends(get_authenticate_user_service),
) -> LoginResponse:
    result = await service.execute(
        subdomain=request.subdomain, email=request.email, password=request.password
    )
    return _login_response(result)


@router.post("/login/phone", response_model=LoginResponse)
async def login_phone(
    request: PhoneLoginRequest,
    service: AuthenticateUserService = Depends(get_authenticate_user_service),
) -> LoginResponse:
    result = await service.execute_phone(
        subdomain=request.subdomain, firebase_id_token=request.firebase_id_token
    )
    return _login_response(result)


@router.post("/platform-handoff", response_model=LoginResponse)
async def platform_handoff(
    request: PlatformHandoffRequest,
    service: PlatformHandoffService = Depends(get_platform_handoff_service),
) -> LoginResponse:
    """Exchanges a Platform Identity token for a normal local Career
    Compass AI session — see
    docs/adr/ADR-010-platform-identity-integration.md. Public (no
    Authorization header required): the platform token itself is the
    proof of identity being exchanged here."""
    result = await service.execute(
        platform_token=request.platform_token, requested_scope=request.org_id
    )
    return _login_response(result)


@router.post("/platform-account-deleted", status_code=status.HTTP_204_NO_CONTENT)
async def platform_account_deleted(
    request: PlatformAccountDeletedRequest,
    service: PlatformAccountDeletionService = Depends(get_platform_account_deletion_service),
) -> None:
    """The Hub calls this, best-effort, right after deleting an account
    that held a career_compass_ai entitlement — see platform's own
    DeleteAccountService. Public (no Authorization header): the signed
    deletion-assertion token itself is the proof, same shape as
    /platform-handoff. Idempotent — see PlatformAccountDeletionService's
    own docstring for how both the Personal and Enterprise cases
    resolve."""
    assertion = verify_platform_deletion_assertion(request.token)
    await service.execute(
        platform_account_id=assertion.account_id, email=assertion.email, org_id=assertion.org_id
    )


@router.post("/signup/verify", response_model=LoginResponse)
async def signup_verify(
    request: VerifySignupRequest,
    service: VerifySignupService = Depends(get_verify_signup_service),
) -> LoginResponse:
    result = await service.execute(token=request.token)
    return _login_response(result)


@router.post("/password-reset/request", response_model=RequestPasswordResetResponse)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    service: RequestPasswordResetService = Depends(get_request_password_reset_service),
) -> RequestPasswordResetResponse:
    await service.execute(subdomain=request.subdomain, email=request.email)
    return RequestPasswordResetResponse()


@router.post("/password-reset/confirm", response_model=ResetPasswordResponse)
async def confirm_password_reset(
    request: ResetPasswordRequest,
    service: ResetPasswordService = Depends(get_reset_password_service),
) -> ResetPasswordResponse:
    await service.execute(token=request.token, new_password=request.new_password)
    return ResetPasswordResponse()


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
        visa_status=result.visa_status,
        linkedin_url=result.linkedin_url,
        other_professional_url=result.other_professional_url,
        middle_name=result.middle_name,
        handle=result.handle,
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
        visa_status=request.visa_status,
        linkedin_url=request.linkedin_url,
        other_professional_url=request.other_professional_url,
        middle_name=request.middle_name,
        handle=request.handle,
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
        visa_status=result.visa_status,
        linkedin_url=result.linkedin_url,
        other_professional_url=result.other_professional_url,
        middle_name=result.middle_name,
        handle=result.handle,
        roles=list(result.roles),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    identity: IdentityClaims = Depends(get_current_identity),
    service: DeleteAccountService = Depends(get_delete_account_service),
) -> None:
    await service.execute(tenant_id=UUID(identity.tenant_id))


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
