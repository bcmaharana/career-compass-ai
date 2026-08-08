"""AI Platform API routes — model preference (Phase 4 follow-up).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service, same as the
chat router — a caller only ever reads/writes their own preference, so
no extra RBAC permission is required beyond a valid identity.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_identity, get_model_preference_service
from app.api.v1.ai_platform.schemas import (
    ModelOptionResponse,
    ModelSelectionResponse,
    SetModelPreferenceRequest,
    display_name,
)
from app.application.ai_platform.model_preference_service import (
    ModelPreferenceService,
    ModelSelection,
)
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(tags=["ai-platform"])


def _selection_response(selection: ModelSelection) -> ModelSelectionResponse:
    return ModelSelectionResponse(
        available=[
            ModelOptionResponse(
                id=UUID(model.id),
                provider=model.provider,
                model_name=model.model_name,
                display_name=display_name(model.model_name),
                is_default=model.is_default,
            )
            for model in selection.available
        ],
        selected_id=UUID(selection.selected_id),
    )


@router.get("/ai-platform/models", response_model=ModelSelectionResponse)
async def get_model_selection(
    identity: IdentityClaims = Depends(get_current_identity),
    service: ModelPreferenceService = Depends(get_model_preference_service),
) -> ModelSelectionResponse:
    selection = await service.get_selection(UUID(identity.tenant_id), UUID(identity.user_id))
    return _selection_response(selection)


@router.patch("/ai-platform/model-preference", response_model=ModelSelectionResponse)
async def set_model_preference(
    request: SetModelPreferenceRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ModelPreferenceService = Depends(get_model_preference_service),
) -> ModelSelectionResponse:
    selection = await service.set_preference(
        UUID(identity.tenant_id), UUID(identity.user_id), request.model_version_id
    )
    return _selection_response(selection)
