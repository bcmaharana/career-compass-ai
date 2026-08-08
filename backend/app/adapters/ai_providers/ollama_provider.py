"""Ollama provider adapter — implements LLMProviderInterface against a
locally-running Ollama server (Phase 4 follow-up: user-selectable local
models alongside the Anthropic-hosted ones).

Ollama has no official Python SDK the way Anthropic does — this is a
plain httpx call against its REST API, the same "no SDK, use httpx"
shape as app/adapters/quotes/zen_quotes_provider.py. `num_predict` is
Ollama's equivalent of `max_tokens`; `prompt_eval_count`/`eval_count`
are its equivalent of input/output token counts.
"""

from __future__ import annotations

import time

import httpx

from app.adapters.ai_providers.errors import AIProviderError
from app.ai_platform.llm_service.provider_interface import LLMRequest, LLMResponse
from app.core.config import Settings

# Local inference on modest hardware (CPU, or a small GPU) is far
# slower than a hosted API — a generous timeout avoids spuriously
# failing a request that's simply still generating. 180s was the
# original figure (fine for a short chat reply, max_tokens=1000) but
# proved too short in practice for Resume Intelligence's much longer
# prompt (a full resume's text, up to 15000 chars) and larger
# max_tokens (2500) — a real extraction on qwen2.5:7b/CPU was observed
# taking up to ~280s. Raised to 600s as the default for every use case
# that doesn't specify its own (LLMRequest.timeout_seconds, added later
# once 600s itself proved too short for a longer, more detailed resume-
# extraction prompt — see that field's own docstring for the specific
# incident).
_REQUEST_TIMEOUT_SECONDS = 600.0


class OllamaProvider:
    """Implements LLMProviderInterface against Ollama's /api/chat endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url

    async def generate(self, request: LLMRequest) -> LLMResponse:
        options: dict[str, object] = {"num_predict": request.max_tokens}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        timeout_seconds = request.timeout_seconds or _REQUEST_TIMEOUT_SECONDS

        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": request.model_name,
                        "messages": [{"role": "user", "content": request.rendered_prompt}],
                        "stream": False,
                        "options": options,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            # httpx's timeout exceptions stringify to an empty message by
            # default (str(exc) == "") — without this dedicated branch,
            # the generic HTTPError handler below produced the genuinely
            # unhelpful "Ollama request failed: " with nothing after the
            # colon, observed live during Resume Intelligence testing.
            raise AIProviderError(
                f"Ollama didn't respond within {timeout_seconds:.0f}s — the model may "
                "still be loading, or this request is too large for local hardware to process "
                "quickly. Try again, or switch to a faster model in Settings > AI Model.",
                code="AI_PROVIDER_REQUEST_FAILED",
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Ollama request failed: {exc}", code="AI_PROVIDER_REQUEST_FAILED"
            ) from exc
        latency_ms = (time.perf_counter() - started_at) * 1000

        return LLMResponse(
            text=payload.get("message", {}).get("content", ""),
            prompt_version_id=request.prompt_version_id,
            model_version_id=request.model_version_id,
            input_tokens=payload.get("prompt_eval_count", 0),
            output_tokens=payload.get("eval_count", 0),
            latency_ms=latency_ms,
        )
