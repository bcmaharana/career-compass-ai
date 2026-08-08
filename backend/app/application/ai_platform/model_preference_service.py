"""Lets a user choose which AI Platform model powers their own chats,
from the catalog of currently-selectable ("active") models.

Self-service, same ownership pattern as UpdateUserProfileService — a
user only ever reads/writes their own preference, identified by the
already-verified identity claims the API layer resolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.ai_platform.models.registry import ModelCatalog, ModelVersion
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.repositories import UserRepository


@dataclass(slots=True)
class ModelSelection:
    available: list[ModelVersion]
    selected_id: str


class ModelPreferenceService:
    def __init__(self, models: ModelCatalog, users: UserRepository) -> None:
        self._models = models
        self._users = users

    async def get_selection(self, tenant_id: UUID, user_id: UUID) -> ModelSelection:
        available = await self._models.list_active()
        selected = await self._models.get_active_model(
            tenant_id=str(tenant_id), user_id=str(user_id)
        )
        return ModelSelection(available=available, selected_id=selected.id)

    async def set_preference(
        self, tenant_id: UUID, user_id: UUID, model_version_id: UUID | None
    ) -> ModelSelection:
        user = await self._users.get_by_id(tenant_id, user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")

        if model_version_id is not None:
            model = await self._models.get_by_id(str(model_version_id))
            if model is None or model.status != "active":
                raise ValidationError(
                    "That model is not available for selection.", code="MODEL_NOT_SELECTABLE"
                )

        user.preferred_model_version_id = model_version_id
        await self._users.update(user)

        return await self.get_selection(tenant_id, user_id)
