"""Anthropic provider adapter — the real implementation of
LLMProviderInterface (Phase 4).

Only this module (and the `anthropic` package it wraps) knows anything
about Anthropic's SDK. Everything upstream — LLMService, application
services — talks to the provider-agnostic LLMRequest/LLMResponse shapes
only, per docs/architecture/ai-platform-architecture.md.
"""

from __future__ import annotations

import time

import anthropic

from app.adapters.ai_providers.errors import AIProviderError
from app.ai_platform.llm_service.provider_interface import LLMRequest, LLMResponse
from app.core.config import Settings


class AnthropicProvider:
    """Implements LLMProviderInterface against the Anthropic Messages API."""

    def __init__(self, settings: Settings) -> None:
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if self._client is None:
            raise AIProviderError(
                "Anthropic API key is not configured (ANTHROPIC_API_KEY).",
                code="AI_PROVIDER_NOT_CONFIGURED",
            )

        started_at = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=request.model_name,
                max_tokens=request.max_tokens,
                messages=[{"role": "user", "content": request.rendered_prompt}],
                temperature=(
                    request.temperature if request.temperature is not None else anthropic.omit
                ),
            )
        except anthropic.APIError as exc:
            raise AIProviderError(
                f"Anthropic API request failed: {exc}", code="AI_PROVIDER_REQUEST_FAILED"
            ) from exc
        latency_ms = (time.perf_counter() - started_at) * 1000

        text = "".join(block.text for block in response.content if block.type == "text")

        return LLMResponse(
            text=text,
            prompt_version_id=request.prompt_version_id,
            model_version_id=request.model_version_id,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )
