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

NOT CURRENTLY WIRED INTO THE APP (as of 2026-09-08). This was the
*only* embedding provider ever actually implemented for CIKG semantic
search's vector-similarity signal (cikg-semantic-search.md's other
planned option, Voyage AI, was never built) — search now runs on graph
traversal + full-text only (see
app/application/career_intelligence/search_service.py's module
docstring). Reason: prod's Oracle Cloud Always Free VM (2 shared ARM
cores, no GPU) can't run Ollama at all, so the vector-similarity signal
could never work in prod regardless of what dev did — search there was
always going to degrade to graph/full-text in practice. Once that was
true, there was no real reason to keep dev exercising the one code path
prod could never use. This class still implements a real, working
EmbeddingProviderInterface — reactivating vector search means either
reinstalling Ollama for local dev/testing, or (more realistically for
prod) implementing the Voyage AI adapter the original design already
scoped out and wiring either provider back into
app/api/dependencies.py's get_search_service (see git history around
2026-09-08 for the exact removed wiring) and
scripts/embed_cikg_content.py's own construction of the provider.
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
