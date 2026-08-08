"""Dashboard System Status API route.

Thin per backend-architecture.md. Reports live reachability for every
runtime dependency this app has — see SystemStatusService's docstring
for why this is deliberately status-only, no restart execution.
Self-service, authenticated data (not tenant-scoped — infra status is
the same for everyone) so this only depends on get_current_identity,
the same convention quote-of-the-day uses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_identity, get_system_status_service
from app.api.v1.system_status.schemas import (
    RateLimitInfoResponse,
    ServiceStatusResponse,
    SystemStatusResponse,
)
from app.application.system_status.system_status_service import SystemStatusService
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(tags=["system-status"])


@router.get("/system-status", response_model=SystemStatusResponse)
async def get_system_status(
    identity: IdentityClaims = Depends(get_current_identity),
    service: SystemStatusService = Depends(get_system_status_service),
) -> SystemStatusResponse:
    result = await service.check_all()
    return SystemStatusResponse(
        services=[
            ServiceStatusResponse(
                name=s.name,
                label=s.label,
                status=s.status,
                detail=s.detail,
                fix_command=s.fix_command,
                rate_limit=(
                    RateLimitInfoResponse(
                        limit_requests=s.rate_limit.limit_requests,
                        remaining_requests=s.rate_limit.remaining_requests,
                        reset_requests=s.rate_limit.reset_requests,
                        limit_tokens=s.rate_limit.limit_tokens,
                        remaining_tokens=s.rate_limit.remaining_tokens,
                        reset_tokens=s.rate_limit.reset_tokens,
                        observed_at=s.rate_limit.observed_at,
                    )
                    if s.rate_limit is not None
                    else None
                ),
            )
            for s in result.services
        ],
        checked_at=result.checked_at,
    )
