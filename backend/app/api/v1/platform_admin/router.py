"""Platform-admin API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Every route past /me is
gated by require_platform_permission — the cross-tenant equivalent of
require_permission (see app/api/dependencies.py) — rather than the
tenant-scoped RBAC engine every other domain in this app uses.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_identity,
    get_platform_admin_repository,
    get_platform_admin_service,
    get_platform_settings_service,
    require_platform_permission,
)
from app.api.v1.platform_admin.schemas import (
    GrantPlatformAdminRequest,
    MyPlatformAdminResponse,
    PlatformAdminGrantResponse,
    PlatformPermissionResponse,
    PlatformSettingResponse,
    UpdatePlatformAdminRequest,
    UpdatePlatformSettingRequest,
)
from app.adapters.db.repositories.platform_admin import SqlAlchemyPlatformAdminRepository
from app.application.platform_admin.grant_service import PlatformAdminService
from app.application.platform_admin.settings_service import PlatformSettingsService
from app.core.identity_provider_interface import IdentityClaims
from app.domain.platform_admin.entities import PlatformAdminGrant, PlatformSetting
from app.domain.platform_admin.permissions import (
    ALL_PLATFORM_PERMISSIONS,
    PLATFORM_ADMINS_MANAGE,
    PLATFORM_SETTINGS_EDIT,
    PLATFORM_SETTINGS_VIEW,
)

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])


def _grant_response(grant: PlatformAdminGrant) -> PlatformAdminGrantResponse:
    return PlatformAdminGrantResponse(
        id=grant.id,
        tenant_id=grant.tenant_id,
        user_id=grant.user_id,
        email=grant.email,
        full_name=grant.full_name,
        permission_codes=sorted(grant.permission_codes),
        granted_at=grant.granted_at,
        granted_by_user_id=grant.granted_by_user_id,
    )


def _setting_response(setting: PlatformSetting) -> PlatformSettingResponse:
    return PlatformSettingResponse(
        id=setting.id,
        key=setting.key,
        value=setting.value,
        description=setting.description,
        updated_at=setting.updated_at,
        updated_by_user_id=setting.updated_by_user_id,
    )


@router.get("/me", response_model=MyPlatformAdminResponse)
async def get_my_platform_admin_grant(
    identity: IdentityClaims = Depends(get_current_identity),
    grants: SqlAlchemyPlatformAdminRepository = Depends(get_platform_admin_repository),
) -> MyPlatformAdminResponse:
    grant = await grants.get_for_user(UUID(identity.tenant_id), UUID(identity.user_id))
    return MyPlatformAdminResponse(
        permission_codes=sorted(grant.permission_codes) if grant else []
    )


@router.get(
    "/permissions",
    response_model=list[PlatformPermissionResponse],
    dependencies=[Depends(require_platform_permission(PLATFORM_ADMINS_MANAGE))],
)
async def list_platform_permissions() -> list[PlatformPermissionResponse]:
    return [
        PlatformPermissionResponse(code=code, description=description)
        for code, description in ALL_PLATFORM_PERMISSIONS
    ]


@router.get(
    "/settings",
    response_model=list[PlatformSettingResponse],
    # Edit implies view — see require_platform_permission's docstring.
    dependencies=[
        Depends(require_platform_permission(PLATFORM_SETTINGS_VIEW, PLATFORM_SETTINGS_EDIT))
    ],
)
async def list_platform_settings(
    service: PlatformSettingsService = Depends(get_platform_settings_service),
) -> list[PlatformSettingResponse]:
    settings = await service.list_all()
    return [_setting_response(s) for s in settings]


@router.patch(
    "/settings/{key}",
    response_model=PlatformSettingResponse,
    dependencies=[Depends(require_platform_permission(PLATFORM_SETTINGS_EDIT))],
)
async def update_platform_setting(
    key: str,
    request: UpdatePlatformSettingRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PlatformSettingsService = Depends(get_platform_settings_service),
) -> PlatformSettingResponse:
    setting = await service.set(
        key=key,
        value=request.value,
        description=request.description,
        updated_by_user_id=UUID(identity.user_id),
    )
    return _setting_response(setting)


@router.get(
    "/admins",
    response_model=list[PlatformAdminGrantResponse],
    dependencies=[Depends(require_platform_permission(PLATFORM_ADMINS_MANAGE))],
)
async def list_platform_admins(
    service: PlatformAdminService = Depends(get_platform_admin_service),
) -> list[PlatformAdminGrantResponse]:
    grants = await service.list_admins()
    return [_grant_response(g) for g in grants]


@router.post(
    "/admins",
    response_model=PlatformAdminGrantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_platform_permission(PLATFORM_ADMINS_MANAGE))],
)
async def grant_platform_admin(
    request: GrantPlatformAdminRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PlatformAdminService = Depends(get_platform_admin_service),
) -> PlatformAdminGrantResponse:
    grant = await service.grant(
        email=request.email,
        subdomain=request.subdomain,
        permission_codes=frozenset(request.permission_codes),
        granted_by_user_id=UUID(identity.user_id),
    )
    return _grant_response(grant)


@router.patch(
    "/admins/{grant_id}",
    response_model=PlatformAdminGrantResponse,
    dependencies=[Depends(require_platform_permission(PLATFORM_ADMINS_MANAGE))],
)
async def update_platform_admin(
    grant_id: UUID,
    request: UpdatePlatformAdminRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PlatformAdminService = Depends(get_platform_admin_service),
) -> PlatformAdminGrantResponse:
    grant = await service.update_permissions(
        grant_id=grant_id,
        permission_codes=frozenset(request.permission_codes),
        granted_by_user_id=UUID(identity.user_id),
    )
    return _grant_response(grant)


@router.delete(
    "/admins/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_platform_permission(PLATFORM_ADMINS_MANAGE))],
)
async def revoke_platform_admin(
    grant_id: UUID,
    service: PlatformAdminService = Depends(get_platform_admin_service),
) -> None:
    await service.revoke(grant_id=grant_id)
