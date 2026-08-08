"""SQLAlchemy-backed implementations of the AI Platform's PromptRegistry,
ModelRegistry, and InvocationLogger Protocols (Phase 4 — replaces the
Phase 0 in-memory reference implementations for real traffic).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    AIInvocationModel,
    ModelVersionModel,
    PromptVersionModel,
    UserModel,
)
from app.ai_platform.governance.invocation_logger import InvocationRecord
from app.ai_platform.models.registry import ModelVersion
from app.ai_platform.prompts.registry import PromptVersion
from app.core.exceptions import NotFoundError


def _prompt_to_domain(model: PromptVersionModel) -> PromptVersion:
    return PromptVersion(
        id=str(model.id),
        name=model.name,
        version=model.version,
        template=model.template,
        status=model.status,
        owner=model.owner,
        approved_by=model.approved_by,
    )


def _model_to_domain(model: ModelVersionModel) -> ModelVersion:
    return ModelVersion(
        id=str(model.id),
        provider=model.provider,
        model_name=model.model_name,
        version=model.version,
        status=model.status,
        cost_per_1k_tokens=float(model.cost_per_1k_tokens),
        is_default=model.is_default,
    )


class SqlAlchemyPromptRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_version(self, *, use_case: str) -> PromptVersion:
        result = await self._session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.name == use_case, PromptVersionModel.status == "approved")
            .order_by(PromptVersionModel.version.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError(
                f"No approved prompt version registered for use case '{use_case}'",
                code="PROMPT_NOT_FOUND",
            )
        return _prompt_to_domain(model)


class SqlAlchemyModelRegistry:
    """Implements both ModelRegistry (LLMService's narrow port) and
    ModelCatalog (ModelPreferenceService's broader read/write needs) —
    see app/ai_platform/models/registry.py for why they're split."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion:
        if user_id is not None:
            preferred = await self._preferred_model(user_id)
            if preferred is not None:
                return preferred

        result = await self._session.execute(
            select(ModelVersionModel)
            .where(ModelVersionModel.status == "active", ModelVersionModel.is_default.is_(True))
            .order_by(ModelVersionModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            # Fallback for a catalog with no row explicitly marked
            # default (shouldn't happen once seeded, but fail open to
            # "most recently added active model" rather than erroring).
            result = await self._session.execute(
                select(ModelVersionModel)
                .where(ModelVersionModel.status == "active")
                .order_by(ModelVersionModel.created_at.desc())
                .limit(1)
            )
            model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError("No active model configured", code="MODEL_NOT_CONFIGURED")
        return _model_to_domain(model)

    async def _preferred_model(self, user_id: str) -> ModelVersion | None:
        user_result = await self._session.execute(
            select(UserModel.preferred_model_version_id).where(UserModel.id == UUID(user_id))
        )
        preferred_id = user_result.scalar_one_or_none()
        if preferred_id is None:
            return None

        model_result = await self._session.execute(
            select(ModelVersionModel).where(
                ModelVersionModel.id == preferred_id, ModelVersionModel.status == "active"
            )
        )
        preferred_model = model_result.scalar_one_or_none()
        return _model_to_domain(preferred_model) if preferred_model is not None else None

    async def list_active(self) -> list[ModelVersion]:
        result = await self._session.execute(
            select(ModelVersionModel)
            .where(ModelVersionModel.status == "active")
            .order_by(ModelVersionModel.provider, ModelVersionModel.model_name)
        )
        return [_model_to_domain(model) for model in result.scalars().all()]

    async def get_by_id(self, model_version_id: str) -> ModelVersion | None:
        model = await self._session.get(ModelVersionModel, UUID(model_version_id))
        return _model_to_domain(model) if model is not None else None


class SqlAlchemyInvocationLogger:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log_invocation(self, record: InvocationRecord) -> None:
        model = AIInvocationModel(
            tenant_id=UUID(record.tenant_id) if record.tenant_id else None,
            user_id=UUID(record.user_id) if record.user_id else None,
            prompt_version_id=UUID(record.prompt_version_id),
            model_version_id=UUID(record.model_version_id),
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            latency_ms=record.latency_ms,
        )
        self._session.add(model)
        await self._session.flush()
