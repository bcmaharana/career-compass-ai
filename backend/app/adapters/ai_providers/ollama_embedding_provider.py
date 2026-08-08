"""Ollama embedding provider adapter — implements
EmbeddingProviderInterface against a locally-running Ollama server
(CIKG MVP 2A, cikg-semantic-search.md's "Ollama-based free embedding
path first").

Mirrors app/adapters/ai_providers/ollama_provider.py's shape exactly:
no official Ollama Python SDK, so this is a plain httpx call against
its REST API. Ollama's `/api/embed` endpoint (not the older singular
`/api/embeddings`) takes a batch of inputs and returns one embedding
per input in the same order — used here rather than looping one call
per text.
"""

from __future__ import annotations

import httpx

from app.adapters.ai_providers.errors import AIProviderError
from app.core.config import Settings

_REQUEST_TIMEOUT_SECONDS = 180.0


class OllamaEmbeddingProvider:
    """Implements EmbeddingProviderInterface against Ollama's /api/embed
    endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url

    async def embed(self, *, texts: list[str], model_name: str) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": model_name, "input": texts},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Ollama embedding request failed: {exc}", code="AI_PROVIDER_REQUEST_FAILED"
            ) from exc

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise AIProviderError(
                "Ollama embedding response was malformed or incomplete.",
                code="AI_PROVIDER_REQUEST_FAILED",
            )
        return embeddings
