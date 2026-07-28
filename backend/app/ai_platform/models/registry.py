"""Model registry structure.

Tracks which provider/model/version is active and its status, so
switching or retiring a model is a data change, not a code change.

Phase 0 status: interface + in-memory reference implementation. The real
implementation (Phase 4) is backed by the `ModelVersion` database table.
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


class ModelRegistry(Protocol):
    """Contract for resolving the active model for a tenant/use case."""

    async def get_active_model(self, *, tenant_id: str | None = None) -> ModelVersion:
        """Return the currently active ModelVersion.

        `tenant_id` is accepted now so tenant-specific model policy
        (e.g., an enterprise tenant restricted to a specific model tier)
        can be layered in later without changing the call signature.

        Raises app.core.exceptions.NotFoundError if no active model is
        configured.
        """
        ...


class InMemoryModelRegistry:
    """Reference implementation used in tests and local development
    before the real database-backed registry lands in Phase 4.
    """

    def __init__(self) -> None:
        self._active: ModelVersion | None = None

    def set_active(self, model: ModelVersion) -> None:
        self._active = model

    async def get_active_model(self, *, tenant_id: str | None = None) -> ModelVersion:
        from app.core.exceptions import NotFoundError

        if self._active is None:
            raise NotFoundError("No active model configured", code="MODEL_NOT_CONFIGURED")
        return self._active
