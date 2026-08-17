"""Learning Intelligence API routes (Phase 7).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity — same as
every career-profile route.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_identity,
    get_learning_item_service,
    get_learning_recommendation_service,
)
from app.api.v1.career_profile.schemas import MoveRequest
from app.api.v1.learning_intelligence.schemas import (
    LearningItemRequest,
    LearningItemResponse,
    LearningItemUpdateRequest,
    LearningRecommendationResponse,
    SkillRecommendationResponse,
)
from app.application.learning_intelligence.learning_item_service import LearningItemService
from app.application.learning_intelligence.learning_recommendation_service import (
    LearningRecommendationService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.learning_intelligence.entities import LearningItem, LearningRecommendationSet

router = APIRouter(tags=["learning-intelligence"])


def _item_response(item: LearningItem) -> LearningItemResponse:
    return LearningItemResponse(
        id=item.id,
        title=item.title,
        provider=item.provider,
        url=item.url,
        status=item.status,
        target_role_id=item.target_role_id,
        notes=item.notes,
        started_at=item.started_at,
        completed_at=item.completed_at,
        created_at=item.created_at,
    )


@router.get("/learning/items", response_model=list[LearningItemResponse])
async def list_learning_items(
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningItemService = Depends(get_learning_item_service),
) -> list[LearningItemResponse]:
    items = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_item_response(i) for i in items]


@router.post(
    "/learning/items", response_model=LearningItemResponse, status_code=status.HTTP_201_CREATED
)
async def add_learning_item(
    request: LearningItemRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningItemService = Depends(get_learning_item_service),
) -> LearningItemResponse:
    item = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        title=request.title,
        provider=request.provider,
        url=request.url,
        target_role_id=request.target_role_id,
        notes=request.notes,
        started_at=request.started_at,
    )
    return _item_response(item)


@router.patch("/learning/items/{item_id}", response_model=LearningItemResponse)
async def update_learning_item(
    item_id: UUID,
    request: LearningItemUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningItemService = Depends(get_learning_item_service),
) -> LearningItemResponse:
    item = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        item_id=item_id,
        title=request.title,
        provider=request.provider,
        url=request.url,
        status=request.status,
        target_role_id=request.target_role_id,
        notes=request.notes,
        started_at=request.started_at,
        completed_at=request.completed_at,
    )
    return _item_response(item)


@router.delete("/learning/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learning_item(
    item_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningItemService = Depends(get_learning_item_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), item_id=item_id
    )


@router.post("/learning/items/{item_id}/move", response_model=list[LearningItemResponse])
async def move_learning_item(
    item_id: UUID,
    request: MoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningItemService = Depends(get_learning_item_service),
) -> list[LearningItemResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        item_id=item_id,
        direction=request.direction,
    )
    items = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_item_response(i) for i in items]


def _skill_recommendation(data: dict[str, object]) -> SkillRecommendationResponse:
    resources = data.get("resources")
    return SkillRecommendationResponse(
        skill=str(data.get("skill", "")),
        resources=[str(x) for x in resources] if isinstance(resources, list) else [],
        summary=str(data.get("summary", "")),
    )


def _recommendation_response(rec_set: LearningRecommendationSet) -> LearningRecommendationResponse:
    return LearningRecommendationResponse(
        target_role_id=rec_set.target_role_id,
        status=rec_set.status,
        generated_at=rec_set.generated_at,
        recommendations=(
            [_skill_recommendation(r) for r in rec_set.recommendations]
            if rec_set.recommendations is not None
            else None
        ),
        error_message=rec_set.error_message,
    )


@router.get("/learning/recommendations", response_model=LearningRecommendationResponse)
async def get_learning_recommendations(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningRecommendationService = Depends(get_learning_recommendation_service),
) -> LearningRecommendationResponse:
    rec_set = await service.get_or_generate(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return _recommendation_response(rec_set)


@router.post("/learning/recommendations/regenerate", response_model=LearningRecommendationResponse)
async def regenerate_learning_recommendations(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: LearningRecommendationService = Depends(get_learning_recommendation_service),
) -> LearningRecommendationResponse:
    rec_set = await service.get_or_generate(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        force_regenerate=True,
    )
    return _recommendation_response(rec_set)
