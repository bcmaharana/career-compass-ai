"""LLMService — the single entry point application services call to
invoke the AI Platform (Phase 4 real wiring).

Orchestrates the four pieces described in
docs/architecture/ai-platform-architecture.md: resolves the active
approved prompt for a use case, resolves the model to use (a user's own
explicit preference if set, else the platform default — see
app/ai_platform/models/registry.py's ModelRegistry.get_active_model),
renders the prompt template, dispatches to the right provider adapter,
and logs the invocation for governance — application services never
touch a provider, prompt registry, model registry, or invocation logger
directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from app.ai_platform.governance.invocation_logger import InvocationLogger, InvocationRecord
from app.ai_platform.llm_service.provider_interface import LLMProviderInterface, LLMRequest
from app.ai_platform.models.registry import ModelRegistry
from app.ai_platform.prompts.registry import PromptRegistry
from app.core.exceptions import CareerCompassError


class ProviderNotConfiguredError(CareerCompassError):
    """Raised when a ModelVersion names a provider with no matching
    entry in LLMService's `providers` map — e.g. a model catalog row
    for a provider whose adapter hasn't been wired up yet."""

    code = "AI_PROVIDER_NOT_CONFIGURED"


class LLMServiceInterface(Protocol):
    """Contract application services depend on — lets tests substitute a
    fake without constructing a real LLMService (which needs a live
    provider, prompt registry, and model registry)."""

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        max_tokens: int = 1000,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str: ...


class LLMService:
    def __init__(
        self,
        *,
        providers: Mapping[str, LLMProviderInterface],
        prompts: PromptRegistry,
        models: ModelRegistry,
        invocations: InvocationLogger,
    ) -> None:
        #: Keyed by ModelVersion.provider (e.g. "anthropic") — one entry
        #: per adapter in app/adapters/ai_providers/. Adding a new
        #: provider (e.g. Ollama) is registering it here plus a
        #: model_versions row naming it, not a change to this class.
        self._providers = providers
        self._prompts = prompts
        self._models = models
        self._invocations = invocations

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        max_tokens: int = 1000,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        prompt_version = await self._prompts.get_active_version(use_case=use_case)
        model_version = await self._models.get_active_model(
            tenant_id=str(tenant_id) if tenant_id is not None else None,
            user_id=str(user_id) if user_id is not None else None,
        )

        provider = self._providers.get(model_version.provider)
        if provider is None:
            raise ProviderNotConfiguredError(
                f"No provider adapter registered for '{model_version.provider}'."
            )

        request = LLMRequest(
            prompt_version_id=str(prompt_version.id),
            model_version_id=str(model_version.id),
            model_name=model_version.model_name,
            rendered_prompt=prompt_version.template.format(**input_variables),
            input_variables=input_variables,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        response = await provider.generate(request)

        await self._invocations.log_invocation(
            InvocationRecord(
                prompt_version_id=request.prompt_version_id,
                model_version_id=request.model_version_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                user_id=str(user_id) if user_id is not None else None,
            )
        )

        return response.text
