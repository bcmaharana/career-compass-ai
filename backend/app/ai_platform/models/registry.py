"""Model registry structure.

Tracks which provider/model/version is active and its status, so
switching or retiring a model is a data change, not a code change.

Phase 4 status: real implementation is
app/adapters/db/repositories/ai_platform.py's SqlAlchemyModelRegistry,
backed by the `model_versions` table. `is_default` marks the single
platform-default model among possibly several "active" (selectable)
ones — see `ModelCatalog` below, which adds the read/write operations
ModelPreferenceService needs beyond the single `get_active_model()`
call LLMService makes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelVersion:
    id: str
    provider: str
    model_name: str
    version: str
    status: str  # "active" | "sunset"
    cost_per_1k_tokens: float
    #: True for the single model used when a user has no explicit
    #: preference set. Exactly one "active" row should carry this.
    is_default: bool = False


class ModelRegistry(Protocol):
    """Contract for resolving the active model for a tenant/user/use case."""

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion:
        """Return the model to use for this call.

        Resolution order: the user's own explicit preference (if set and
        still active) — see ModelCatalog.set_user_preference — else the
        tenant's policy (not yet implemented; `tenant_id` is accepted so
        it can be layered in later without changing the call signature),
        else the platform default (`is_default=True`).

        Raises app.core.exceptions.NotFoundError if no active model is
        configured.
        """
        ...


class ModelCatalog(Protocol):
    """Superset of ModelRegistry — the read/write operations
    ModelPreferenceService needs to list selectable models and manage a
    user's preference. LLMService only ever depends on the narrower
    ModelRegistry above; this Protocol exists so the application layer
    doesn't need to import the concrete SqlAlchemy implementation just
    to type-hint against it.
    """

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion: ...

    async def list_active(self) -> list[ModelVersion]:
        """All selectable (status="active") models, for a picker UI."""
        ...

    async def get_by_id(self, model_version_id: str) -> ModelVersion | None: ...


class InMemoryModelRegistry:
    """Reference implementation used in tests and local development
    before the real database-backed registry lands in Phase 4.
    """

    def __init__(self) -> None:
        self._active: ModelVersion | None = None

    def set_active(self, model: ModelVersion) -> None:
        self._active = model

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion:
        from app.core.exceptions import NotFoundError

        if self._active is None:
            raise NotFoundError("No active model configured", code="MODEL_NOT_CONFIGURED")
        return self._active
